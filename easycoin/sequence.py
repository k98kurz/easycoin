"""
Supports splitting large records into verifiable parts for transmission within.
netaio Message (UDP datagrams). Each Part includes a Merkle Tree inclusion proof.
Parts are cached in segmented LRU caches for receive and send operations,
enabling validation and reconstruction without requiring the full original record.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from merkleasy import Tree
from sqloquent import SqlModel
from easycoin.cache import LRUCache, CacheKind
from easycoin.config import get_config_manager
from easycoin.constants import MAX_PART_SIZE, MAX_SEQUENCE_SIZE
import packify


@dataclass
class Part:
    record_type: str
    record_id: str
    idx: int
    root: bytes
    proof: bytes
    blob: bytes

    def __hash__(self) -> int:
        return hash((self.record_type, self.record_id, self.idx))

    def validate(self) -> bool:
        """Validate the Part. Returns False if `idx` is < 0 or >
            `MAX_SEQUENCE_SIZE`, or if the blob size exceeds
            `MAX_PART_SIZE`, or if the Merkle Tree inclusion proof
            fails verification.
        """
        return (
            self.idx >= 0
            and self.idx <= MAX_SEQUENCE_SIZE
            and len(self.blob) <= MAX_PART_SIZE
            and Tree.verify(self.root, self.blob, self.proof)
        )

    def pack(self) -> bytes:
        return packify.pack((
            self.record_type,
            self.record_id,
            self.idx,
            self.root,
            self.proof,
            self.blob,
        ))

    @classmethod
    def unpack(cls, data: bytes) -> Part:
        return cls(*packify.unpack(data))


@dataclass
class Sequence:
    record_type: str
    record_id: str
    root: bytes
    count: int
    parts: dict[int, Part] = field(default_factory=dict)

    def validate(self) -> bool:
        return (
            type(self.record_type) is str
            and len(self.record_type)
            and type(self.record_id) is str
            and len(self.record_id)
            and type(self.root) is bytes
            and len(self.root) == 32
            and type(self.count) is int
            and self.count > 0
            and self.count <= MAX_SEQUENCE_SIZE
        )

    def has_part(self, idx: int) -> bool:
        return idx in self.parts

    def get_part(self, idx: int) -> Part | None:
        return self.parts.get(idx, None)

    def add_part(self, part: Part) -> None:
        """Attempt to add a part of this sequence. Raises `ValueError`
            if the part does not belong to the sequence or if the
            Merkle Tree inclusion proof is not valid.
        """
        if  (   part.root != self.root
                or part.idx >= self.count
            ):
            raise ValueError('cannot add Part that is not from this Sequence')
        if not part.validate():
            raise ValueError('part.validate() length or Merkle Tree check failed')
        self.parts[part.idx] = part

    def can_reconstruct(self) -> bool:
        """Determine if the original can be reconstructed (i.e. if all
            parts have been received).
        """
        return len(self.parts) == self.count

    def reconstruct(self) -> bytes:
        """Reconstruct the original blob from parts. Raises `ValueError`
            if it cannot be reconstructed.
        """
        if not self.can_reconstruct():
            raise ValueError('cannot reconstruct when missing parts')

        parts = list(self.parts.values())
        parts.sort(key=lambda p: p.idx)
        return b''.join([p.blob for p in parts])

    def pack(self) -> bytes:
        if len(self.parts) == 1 and self.count == 1:
            return packify.pack((
                self.record_type,
                self.record_id,
                self.root,
                self.count,
                self.parts,
            ))
        return packify.pack((
            self.record_type,
            self.record_id,
            self.root,
            self.count,
        ))

    @classmethod
    def unpack(cls, data: bytes) -> Sequence:
        return cls(*packify.unpack(data))


def prepare_sequence(record: packify.Packable) -> Sequence:
    """Packs the record, divides it into parts, calculates the Merkle
        Tree, and prepares a Sequence of Parts.
    """
    record_type = record.__class__.__name__
    record_id = record.id
    blob = record.pack()
    leaves, parts = [], {}
    i = 0
    while i < len(blob):
        leaves.append(blob[i:i+MAX_PART_SIZE])
        i += MAX_PART_SIZE

    if len(leaves) == 1:
        tree = Tree.from_leaves([leaves[0], b''])
    else:
        tree = Tree.from_leaves(leaves)
    for idx, leaf in enumerate(leaves):
        proof = tree.prove(leaf)
        parts[idx] = Part(record_type, record_id, idx, tree.root, proof, leaf)

    sequence = Sequence(record_type, record_id, tree.root, len(parts), parts)
    return sequence


def get_sequence(
        record_type: type, record_id: str, cache_kind: CacheKind
    ) -> Sequence:
    """Try to get the Sequence from the relevant cache. On first cache
        miss, check the other cache and populate primary cache if found.
        On second cache miss, try to create the Sequence and seed the
        cache. Raises `ValueError` if the record cannot be located in
        cache or db.
    """
    conf = get_config_manager()
    scz = conf.get('sequence_cache_size', 20)
    primary_cache = LRUCache.get_instance('sequences', cache_kind, scz)
    key = f'{record_type.__name__}:{record_id}'
    sequence = primary_cache.get(key)

    # cache hit
    if sequence:
        return sequence

    # on first cache miss, try the other cache without updating its LRU order
    other_kind = (
        CacheKind.RECEIVE if cache_kind is CacheKind.SEND else CacheKind.SEND
    )
    second_cache = LRUCache.get_instance('sequences', other_kind, scz)
    sequence = second_cache.peak(key)

    # second cache hit
    if sequence:
        primary_cache.put(key, sequence)
        return sequence

    # on cache miss, prepare sequence and put in cache if it can be done
    record = None
    if issubclass(record_type, SqlModel):
        record = record_type.find(record_id)
    if not record:
        raise ValueError('could not locate the record')
    sequence = prepare_sequence(record)

    # write to caches
    primary_cache.put(key, sequence)
    pcz = conf.get('parts_cache_size', 1000)
    parts_cache = LRUCache.get_instance('parts', cache_kind, pcz)
    for p in sequence.parts.values():
        parts_cache.put(f'{key}:{p.idx}', p)

    return sequence


def get_part(
        record_type: type, record_id: str, cache_kind: CacheKind, idx: int
    ) -> Part:
    """Try to get the Part from the relevant cache. On first cache miss,
        check other cache and populate primary cache if found. Then
        fall through to `get_sequence`, then seed the relevant parts
        cache. Raises `ValueError` if the record cannot be located in
        cache or db.
    """
    conf = get_config_manager()
    pcz = conf.get('parts_cache_size', 1000)
    primary_cache = LRUCache.get_instance('parts', cache_kind, pcz)
    key = f'{record_type.__name__}:{record_id}:{idx}'
    part = primary_cache.get(key)

    # cache hit
    if part:
        return part

    # on first cache miss, check other cache without updating its LRU order
    other_kind = (
        CacheKind.RECEIVE if cache_kind is CacheKind.SEND else CacheKind.SEND
    )
    second_cache = LRUCache.get_instance('parts', other_kind, pcz)
    part = second_cache.peak(key)
    
    # second cache hit
    if part:
        primary_cache.put(key, part)
        return part

    # on second cache miss, fall through to get_sequence
    sequence = get_sequence(record_type, record_id, cache_kind)

    # return part if it was found
    if sequence.has_part(idx):
        return sequence.get_part(idx)

    # data could not be located
    raise ValueError('part data could not be located')


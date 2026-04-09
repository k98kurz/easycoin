from __future__ import annotations
from easycoin.errors import type_assert, value_assert
from enum import IntEnum
from merkleasy import Tree
from sqloquent import HashedModel, RelatedModel, RelatedCollection
import packify


_max_leaves = 1024
_max_chunk_size = 60 * _max_leaves # 61440
_empty_tuple = packify.pack(tuple())


class ChunkKind(IntEnum):
    OUTPUTS = 0
    INPUTS = 1
    TXNS = 2
    PROOFS = 3
    MUTATIONS = 4
    OTHER = 10


class Chunk(HashedModel):
    connection_info: str = ''
    table: str = 'chunks'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'net_id', 'idx', 'kind', 'root', 'parent_ids', 'leaves')
    columns_excluded_from_hash = ('leaves',)
    id: str
    net_id: str
    idx: int
    kind: int
    root: bytes
    parent_ids: str|None
    leaves: bytes
    trustnet: RelatedModel
    snapshots: RelatedCollection
    parents: RelatedCollection
    children: RelatedCollection

    @property
    def kind(self) -> ChunkKind:
        return ChunkKind(self.data['kind'])
    @kind.setter
    def kind(self, val: ChunkKind):
        type_assert(type(val) is ChunkKind, 'Chunk.type must be ChunkKind')
        self.data['kind'] = val.value

    @property
    def leaves(self) -> tuple[bytes]:
        """The leaves of the Merkle tree. Setting this also sets the
            root to the new Merkle tree root. Setting raises `TypeError`
            if setting to something other than `list[bytes]` or
            `ValueError` if the number of leaves exceeds the
            `_max_leaves` (default 256) or if the serialized bytes size
            exceeds `_max_chunk_size` (default 240*256). (These constraints
            are intended to make sure an individual chunk can fit within
            a UDP datagram.
        """
        return packify.unpack(self.data.get('leaves', None) or _empty_tuple)
    @leaves.setter
    def leaves(self, val: list[bytes]):
        type_assert(type(val) is list, 'leaves must be list[bytes]')
        type_assert(all([type(v) is bytes for v in val]),
            'leaves must be list[bytes]')
        value_assert(len(val) <= _max_leaves,
            f'maximum number of leaves is {_max_leaves}')
        packed = packify.pack(tuple(val))
        value_assert(len(packed) <= _max_chunk_size,
            f'maximum chunk size is {_max_chunk_size}; {len(packed)} is too large')
        self.data['leaves'] = packify.pack(tuple(val))
        self.data['root'] = Tree.from_leaves(val).root

    @property
    def root(self) -> bytes:
        """The Merkle root of the data. Cannot be set directly; set the
            leaves instead, and the new root will be calculated and set.
        """
        return self.data.get('root', b'')

    @classmethod
    def create(
            cls, net_id: str, idx: int, kind: ChunkKind, leaves: list[bytes],
            parents: list[str] = []
        ) -> Chunk:
        """Create a Chunk from the required columns/fields. Raises
            `TypeError` for invalid arguments.
        """
        type_assert(type(net_id) is str, 'net_id must be str')
        type_assert(type(idx) is int, 'idx must be int')
        type_assert(type(kind) is ChunkKind, 'kind must be ChunkKind')
        type_assert(type(leaves) in (list, tuple), 'leaves must be list[bytes]')
        type_assert(all([type(l) is bytes for l in leaves]),
            'leaves must be list[bytes]')
        type_assert(type(parents) in (list, tuple), 'parents must be list[str]')
        type_assert(all([type(p) is str for p in parents]),
            'parents must be list[str]')
        c = cls({'net_id': net_id, 'idx': idx, 'kind': kind.value})
        c.leaves = leaves
        c.parent_ids = ','.join(parents)
        return c


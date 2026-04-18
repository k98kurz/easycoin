# easycoin.sequence

Supports splitting large records into verifiable parts for transmission within.
netaio Message (UDP datagrams). Each Part includes a Merkle Tree inclusion
proof. Parts are cached in segmented LRU caches for receive and send operations,
enabling validation and reconstruction without requiring the full original
record.

## Classes

### `Part`

Part(record_type: 'str', record_id: 'str', idx: 'int', root: 'bytes', proof:
'bytes', blob: 'bytes')

#### Annotations

- record_type: str
- record_id: str
- idx: int
- root: bytes
- proof: bytes
- blob: bytes

#### Methods

##### `__init__(record_type: str, record_id: str, idx: int, root: bytes, proof: bytes, blob: bytes):`

##### `validate() -> bool:`

Validate the Part. Returns False if `idx` is < 0 or > `MAX_SEQUENCE_SIZE`, or if
the blob size exceeds `MAX_PART_SIZE`, or if the Merkle Tree inclusion proof
fails verification.

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, inject: dict | None = None) -> Part:`

### `Sequence`

Sequence(record_type: 'str', record_id: 'str', root: 'bytes', count: 'int',
parts: 'dict[int, Part]' = <factory>)

#### Annotations

- record_type: str
- record_id: str
- root: bytes
- count: int
- parts: dict[int, Part]

#### Methods

##### `__init__(record_type: str, record_id: str, root: bytes, count: int, parts: dict[int, Part] = <factory>):`

##### `validate() -> bool:`

##### `has_part(idx: int) -> bool:`

##### `get_part(idx: int) -> Part | None:`

##### `add_part(part: Part) -> None:`

Attempt to add a part of this sequence. Raises `ValueError` if the part does not
belong to the sequence or if the Merkle Tree inclusion proof is not valid.

##### `can_reconstruct() -> bool:`

Determine if the original can be reconstructed (i.e. if all parts have been
received).

##### `reconstruct() -> bytes:`

Reconstruct the original blob from parts. Raises `ValueError` if it cannot be
reconstructed.

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, inject: dict | None = None) -> Sequence:`

## Functions

### `prepare_sequence(record: packify.Packable) -> Sequence:`

Packs the record, divides it into parts, calculates the Merkle Tree, and
prepares a Sequence of Parts.

### `get_sequence(record_type: type, record_id: str, cache_kind: CacheKind) -> Sequence:`

Try to get the Sequence from the relevant cache. On first cache miss, check the
other cache and populate primary cache if found. On second cache miss, try to
create the Sequence and seed the cache. Raises `ValueError` if the record cannot
be located in cache or db.

### `get_part(record_type: type, record_id: str, cache_kind: CacheKind, idx: int) -> Part:`

Try to get the Part from the relevant cache. On first cache miss, check other
cache and populate primary cache if found. Then fall through to `get_sequence`,
then seed the relevant parts cache. Raises `ValueError` if the record cannot be
located in cache or db.

## Values

- `MAX_PART_SIZE`: int
- `MAX_SEQUENCE_SIZE`: int


from sqloquent import HashedModel, RelatedCollection


class TrustNet(HashedModel):
    connection_info: str = ''
    table: str = 'trust_nets'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'lock', 'root', 'members', 'quorum', 'root_witness', 'active')
    columns_excluded_from_hash = ('root', 'members', 'root_witness', 'active')
    id: str
    lock: bytes
    root: bytes|None
    members: str|None
    quorum: int|None
    root_witness: bytes|None
    active: bool
    coins: RelatedCollection
    snapshots: RelatedCollection



from sqloquent import HashedModel, RelatedCollection, RelatedModel


class Snapshot(HashedModel):
    connection_info: str = ''
    table: str = 'snapshots'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'net_id', 'timestamp', 'input_ids', 'output_ids', 'witness')
    id: str
    net_id: str
    timestamp: int
    input_ids: bytes
    output_ids: bytes
    witness: bytes
    trustnet: RelatedModel
    inputs: RelatedCollection
    outputs: RelatedCollection



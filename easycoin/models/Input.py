from sqloquent import SqlModel, RelatedModel


class Input(SqlModel):
    connection_info: str = ''
    table: str = 'inputs'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'wallet_id')
    id: str
    wallet_id: str|None
    coin: RelatedModel



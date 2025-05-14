from sqloquent import SqlModel, Default, RelatedModel


class Output(SqlModel):
    connection_info: str = ''
    table: str = 'outputs'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'wallet_id')
    id: str
    wallet_id: str|None
    coin: RelatedModel


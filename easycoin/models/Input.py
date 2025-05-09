from sqloquent import SqlModel, RelatedModel


class Input(SqlModel):
    connection_info: str = ''
    table: str = 'inputs'
    id_column: str = 'id'
    columns: tuple[str] = ('id',)
    id: str
    coin: RelatedModel



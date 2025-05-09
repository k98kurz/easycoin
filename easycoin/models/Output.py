from sqloquent import SqlModel, Default, RelatedModel


class Output(SqlModel):
    connection_info: str = ''
    table: str = 'outputs'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'spent')
    id: str
    spent: bool|Default[False]
    coin: RelatedModel


from sqloquent import HashedModel, RelatedModel
from .Coin import Coin


class Attestation(HashedModel):
    connection_info: str = ''
    table: str = 'attestations'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'input_id', 'output_id', 'witness')
    id: str
    input_id: str|None
    output_id: str|None
    witness: bytes
    input: RelatedModel
    output: RelatedModel

    def coin(self) -> Coin:
        """Return the related Coin (either input or output)."""
        if self.input_id:
            return Coin.find(self.input_id)
        return Coin.find(self.output_id)

    def runtime_cache(self) -> dict:
        """Return the tapescript runtime cache."""
        return {
            "sigfield1": bytes.fromhex(self.input_id or self.output_id),
        }



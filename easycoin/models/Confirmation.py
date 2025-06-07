from __future__ import annotations
from sqloquent import HashedModel, RelatedModel, RelatedCollection
import packify


class Confirmation(HashedModel):
    connection_info: str = ''
    table: str = 'confirmations'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'net_id', 'txn_id', 'input_ids', 'output_ids', 'witness')
    id: str
    net_id: str
    txn_id: str|None
    input_ids: str|None
    output_ids: str|None
    witness: bytes
    txn: RelatedModel
    inputs: RelatedCollection
    outputs: RelatedCollection

    def pack(self) -> bytes:
        return packify.pack({
            **self.data,
            'txn': self.txn,
            'inputs': [i.pack() for i in self.inputs],
            'outputs': [o.pack() for o in self.outputs],
        })

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> Confirmation:
        unpacked = packify.unpack(data, inject)
        confirmation = cls(unpacked)
        if unpacked.get('txn', None):
            confirmation.txn = unpacked['txn']
        if 'inputs' in unpacked:
            confirmation.inputs = [Coin.unpack(c) for c in unpacked['inputs']]
        if 'outputs' in unpacked:
            confirmation.outputs = [Coin.unpack(c) for c in unpacked['outputs']]

    def runtime_cache(self) -> dict:
        """Return the tapescript runtime cache."""
        input_ids_bytes = packify.pack([bytes.fromhex(i) for i in self.input_ids])
        output_ids_bytes = packify.pack([bytes.fromhex(o) for o in self.output_ids])
        return {
            "sigfield1": b'Confirm',
            "sigfield2": self.net_id_bytes,
            "sigfield3": self.txn_id_bytes,
            "sigfield4": input_ids_bytes,
            "sigfield5": output_ids_bytes,
        }



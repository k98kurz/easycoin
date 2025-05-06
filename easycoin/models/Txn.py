from __future__ import annotations
from hashlib import sha256
from sqloquent import HashedModel, RelatedCollection
from tapescript import run_auth_script
from typing import Protocol
import packify


class UTXOSetInterface(Protocol):
    def add(self, coin_id: bytes):
        ...

    def remove(self, coin_id: bytes):
        ...

    def exists(self, coin_id: bytes) -> bool:
        ...

    def has_been_removed(self, coin_id: bytes) -> bool:
        ...


_empty = packify.pack({})

def type_assert(condition: bool, message: str = 'invalid type'):
    if not condition:
        raise TypeError(message)


class Txn(HashedModel):
    connection_info: str = ''
    table: str = 'txns'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'input_ids', 'output_ids', 'details', 'witness', 'wallet_id')
    columns_excluded_from_hash = ('wallet_id',)
    id: str
    input_ids: str
    output_ids: str
    details: bytes|None
    witness: bytes
    wallet_id: str|None
    inputs: RelatedCollection
    outputs: RelatedCollection

    @property
    def details(self) -> dict:
        return packify.unpack(self.data['witness'] or _empty)
    @details.setter
    def details(self, val: dict):
        type_assert(isinstance(val, dict),
            'details must be dict')
        self.data['details'] = packify.pack(val)

    @property
    def witness(self) -> dict:
        return packify.unpack(self.data['witness'] or _empty)
    @witness.setter
    def witness(self, val: dict[str, bytes]):
        type_assert(isinstance(val, dict),
            'witness must be dict[str, bytes]')
        type_assert(all(isinstance(n, str) for n in val),
            'witness must be dict[str, bytes]')
        type_assert(all(isinstance(val[n], bytes) for n in val),
            'witness must be dict[str, bytes]')
        self.data['witness'] = packify.pack(val)

    @staticmethod
    def minimum_fee(txn: Txn) -> int:
        coins = len(txn.output_ids.split(','))
        return len(txn.data['witness']) + coins * 32

    def validate(self, utxos: UTXOSetInterface) -> bool:
        input_ids = [bytes.fromhex(i) for i in self.input_ids.split(',')]
        for i in input_ids:
            if not utxos.exists(i) or utxos.has_been_removed(i):
                return False

        output_ids = [bytes.fromhex(i) for i in self.output_ids.split(',')]
        for i in output_ids:
            if utxos.exists(i) or utxos.has_been_removed(i):
                return False

        self.inputs().reload()
        self.outputs().reload()

        # make sure each input has satisfactory witness data
        cache_vals = {
            'sigfield1': sha256(b''.join(output_ids)).digest(),
        }
        for coin in self.inputs:
            if coin.id not in self.witness:
                return False
            if not run_auth_script(self.witness[coin.id] + coin.lock, cache_vals):
                return False

        total_spent = Txn.minimum_fee(self)
        for coin in self.outputs:
            total_spent += coin.amount
        total_funding = 0
        for coin in self.inputs:
            total_funding += coin.amount
        if total_spent > total_funding:
            return False

        return True


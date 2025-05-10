from __future__ import annotations
from hashlib import sha256
from sqloquent import HashedModel, RelatedCollection
from tapescript import run_auth_scripts, Script
from typing import Protocol
import packify


class UTXOSetInterface(Protocol):
    def add(self, coin_id: bytes|str):
        ...

    def remove(self, coin_id: bytes|str):
        ...

    def exists(self, coin_id: bytes|str) -> bool:
        ...

    def has_been_removed(self, coin_id: bytes|str) -> bool:
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
        return packify.unpack(self.data.get('details', _empty))
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
        """Calculates the minimum burn required for the transaction."""
        witlen = len(txn.data.get('witness', _empty))
        out_count = len(txn.output_ids.split(','))
        out_len = sum([len(o.preimage(o.data)) for o in txn.outputs])
        return witlen + out_count * 32 + out_len

    def validate(self, utxos: UTXOSetInterface) -> bool:
        input_ids = [bytes.fromhex(i) for i in self.input_ids.split(',') if i]
        for i in input_ids:
            if not utxos.exists(i) or utxos.has_been_removed(i):
                print('non-existant/double-spent input')
                return False

        output_ids = [bytes.fromhex(i) for i in self.output_ids.split(',')]
        for i in output_ids:
            if utxos.exists(i) or utxos.has_been_removed(i):
                print('output already exists or has been spent')
                return False

        self.inputs().reload()
        self.outputs().reload()

        # minting Txn is a special case
        if len(self.inputs) == 0 and len(self.outputs) == 1:
            coin = self.outputs[0]
            #print('mint requires amount <= mint_value and no coin.details')
            return coin.amount <= coin.mint_value() and coin.details is None

        # ensure total spent is less than total funding of EC⁻¹
        total_out = Txn.minimum_fee(self)
        for coin in self.outputs:
            total_out += coin.amount
        total_in = 0
        for coin in self.inputs:
            total_in += coin.amount
        if total_out > total_in:
            print('total_out > total_in')
            return False

        # validate tapescript auth
        for coin in self.inputs:
            if coin.id_bytes not in self.witness:
                print('missing witness')
                return False
            scripts = []
            if coin.details and '_' in coin.details:
                scripts.append(coin.details['_'])
            if coin.id_bytes in self.witness:
                scripts.append(self.witness[coin.id_bytes])
            scripts.append(coin.lock)
            if coin.details:
                # enforce Stamp covenant
                if '$' in coin.details:
                    scripts.append(coin.details['$'])
                else:
                    cdh = sha256(packify.pack(coin.details)).digest()
                    scripts.append(Script.from_src(f'''
                        get_value s"o_len" push d1 equal_verify
                        get_value s"o_det" push x{cdh.hex()} equal_verify
                    '''))
            if not run_auth_scripts(scripts, self.runtime_cache(coin)):
                print('witness validation failed for a lock')
                return False

        # handle new stamps
        for coin in self.outputs:
            if coin.details:
                if b'ML' in coin.details and not run_auth_scripts(
                    [coin.details[b'ML']], self.runtime_cache(coin)
                ):
                    print('stamp creation constraint failed validation')
                    return False

        return True

    def runtime_cache(self, coin: 'Coin'):
        cache = {
            "o_len": len(self.outputs),
            "o_det": [o.data['details'] for o in self.outputs],
            "i_len": len(self.inputs),
            "i_det": coin.data['details'] or b'',
            "sigfield1": coin.id_bytes,
            "sigfield2": sha256(b''.join(sorted([i.id_bytes for i in self.inputs]))).digest(),
            "sigfield3": sha256(b''.join(sorted([o.id_bytes for o in self.outputs]))).digest(),
        }
        return cache


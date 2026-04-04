from __future__ import annotations
from .Coin import Coin
from .errors import type_assert, value_assert
from easycoin.constants import (
    _witfee_mult,
    _witfee_exp,
    _outcountfee_mult,
    _outcountfee_exp,
    _outfee_mult,
    _outfee_exp,
    _infee_mult,
    _infee_exp,
    _outscriptfee_mult,
    _outscriptfee_exp,
    _max_txn_size,
    _empty,
)
from hashlib import sha256
from sqloquent import HashedModel, RelatedCollection, RelatedModel
from tapescript import run_auth_scripts, Script, int_to_bytes
from time import time
import packify


class Txn(HashedModel):
    connection_info: str = ''
    table: str = 'txns'
    id_column: str = 'id'
    columns: tuple[str] = (
        'id', 'timestamp', 'input_ids', 'output_ids', 'details', 'witness',
        'wallet_id',
    )
    columns_excluded_from_hash = ('wallet_id',)
    id: str
    timestamp: int
    input_ids: str
    output_ids: str
    details: bytes|None
    witness: bytes|None
    wallet_id: str|None
    inputs: RelatedCollection
    outputs: RelatedCollection
    wallet: RelatedModel
    attestations: RelatedCollection
    confirmation: RelatedModel

    @property
    def input_ids(self) -> list[str]:
        """The list of input IDs. Setting to a type other than list[str]
            raises TypeError.
        """
        if not self.data.get('input_ids', None):
            return []
        return self.data.get('input_ids').split(',')
    @input_ids.setter
    def input_ids(self, val: list[str]|None):
        type_assert(type(val) in (list, tuple, type(None)),
            'input_ids must be list[str]|None')
        if not val:
            self.data['input_ids'] = None
            return
        type_assert(all([type(s) is str for s in val]),
            'input_ids must be list[str]')
        self.data['input_ids'] = ','.join(sorted(list(set(val))))

    @property
    def output_ids(self) -> list[str]:
        """The list of output IDs. Setting to a type other than list[str]
            raises TypeError. Output IDs will be sorted automatically.
        """
        if not self.data.get('output_ids', None):
            return []
        return self.data.get('output_ids').split(',')
    @output_ids.setter
    def output_ids(self, val: list[str]|None):
        type_assert(type(val) in (list, tuple, type(None)),
            'output_ids must be list[str]|None')
        if not val:
            self.data['output_ids'] = None
            return
        type_assert(all([type(s) is str for s in val]),
            'output_ids must be list[str]|None')
        self.data['output_ids'] = ','.join(sorted(list(set(val))))

    @property
    def details(self) -> dict:
        """Optional transaction details in dict form. Setting raises
            `TypeError` for non-dict values or `packify.UsageError` if a
            type not serializable via packify is used in the dict.
        """
        return packify.unpack(self.data.get('details', None) or _empty)
    @details.setter
    def details(self, val: dict|None):
        type_assert(isinstance(val, dict) or val is None,
            'details must be dict or None')
        self.data['details'] = packify.pack(val) if val is not None else None

    @property
    def witness(self) -> dict[bytes, bytes]:
        """Witness data dict mapping bytes `coin.id` to bytes witness
            script (tapescript byte code).
        """
        return packify.unpack(self.data.get('witness', None) or _empty)
    @witness.setter
    def witness(self, val: dict[bytes, bytes]):
        type_assert(isinstance(val, dict),
            'witness must be dict[bytes, bytes]')
        type_assert(all(isinstance(n, bytes) for n in val),
            'witness must be dict[bytes, bytes]')
        type_assert(all(isinstance(val[n], bytes) for n in val),
            'witness must be dict[bytes, bytes]')
        value_assert(all(len(n) == 32 for n in val),
            'witness keys must each be 32-byte hash')
        self.data['witness'] = packify.pack(val)

    def set_timestamp(self):
        self.timestamp = max([0, *[c.timestamp for c in self.outputs]]) or int(time())

    def save(self) -> Txn:
        if 'timestamp' not in self.data:
            self.set_timestamp()
        return super().save()

    def pack(self) -> bytes:
        return packify.pack({
            **self.data,
            'inputs': [i.pack() for i in self.inputs],
            'outputs': [o.pack() for o in self.outputs],
        })

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> Txn:
        unpacked = packify.unpack(data, inject)
        txn = cls(unpacked)
        if 'inputs' in unpacked:
            txn.inputs = [Coin.unpack(c) for c in unpacked['inputs']]
        if 'outputs' in unpacked:
            txn.outputs = [Coin.unpack(c) for c in unpacked['outputs']]
        return txn

    @staticmethod
    def minimum_fee(txn: Txn) -> int:
        """Calculates the minimum burn required for the transaction."""
        witlen = len(txn.data.get('witness', None) or _empty)
        witfee = int(witlen * _witfee_mult)
        witfee = int(witfee ** _witfee_exp)
        out_count = len(txn.output_ids)
        outcountfee = int(out_count * _outcountfee_mult)
        outcountfee = int(outcountfee ** _outcountfee_exp)
        out_len = sum([len(o.preimage(o.data)) for o in txn.outputs])
        outfee = int(out_len * _outfee_mult)
        outfee = int(outfee ** _outfee_exp)
        in_len = sum([len(i.preimage(i.data)) for i in txn.inputs])
        infee = int(in_len * _infee_mult)
        infee = int(infee ** _infee_exp)
        return witfee + outcountfee + outfee + infee

    def validate(self, debug: bool|str = False, reload: bool = True) -> bool:
        """Runs the transaction validation logic. Returns False if a
            mint Txn has a coin amount that is greater than the mint
            value; or if the total amount in outputs is greater than the
            total amount in inputs; or if the timestamp of an input is
            greater than the timestamp of any output; or if an input lock
            is not fulfilled by a witness script; or if a new stamp is
            not authorized by an 'L' script; or if a transferred stamp
            does not validate against its covenants; or if the serialized
            txn size is greater than 32 KiB. Returns True if all checks
            pass.
        """
        if reload:
            self.inputs().reload()
            self.outputs().reload()

        # reject large txns
        if len(self.pack()) > _max_txn_size:
            print(f'txn > _max_txn_size ({debug})') if debug else ''
            return False

        # minting Txn is a special case
        if len(self.inputs) == 0 and len(self.outputs) == 1:
            coin = self.outputs[0]
            res = coin.amount + Txn.minimum_fee(self) <= coin.mint_value()
            res = res and not coin.details
            if debug and not res:
                print(f'mint: amount <= mint_value and not coin.details ({debug})')
            return res

        # reject large coins
        for coin in [*self.inputs, *self.outputs]:
            if not coin.check_size():
                print(
                    f'excessively large coin.details rejected ({debug})'
                ) if debug else ''
                return False

        # ensure total spent is less than total funding of EC⁻¹
        total_out = Txn.minimum_fee(self)
        for coin in self.outputs:
            total_out += coin.amount
        total_in = 0
        for coin in self.inputs:
            total_in += coin.amount
        if total_out > total_in:
            print(f'total_out > total_in ({debug})') if debug else ''
            return False

        # reject invalid causal ordering
        in_timestamps = [c.timestamp for c in self.inputs]
        out_timestamps = [c.timestamp for c in self.outputs]
        for in_ts in in_timestamps:
            if any([in_ts > out_ts for out_ts in out_timestamps]):
                print(f'input timestamp > output timestamp ({debug})') if debug else ''
                return False
        if not self.timestamp:
            print(f'txn missing timestamp ({debug})') if debug else ''
            return False
        if any([out_ts > self.timestamp for out_ts in out_timestamps]):
            print(f'output timestamp > txn timestamp ({debug})') if debug else ''
            return False

        # validate tapescript auth
        for coin in self.inputs:
            if coin.id_bytes not in self.witness:
                print(f'missing witness; adding empty script ({debug})') if debug else ''
                self.witness = {
                    coin.id_bytes: b'',
                    **self.witness
                }
            scripts = []
            if coin.details and '_' in coin.details:
                scripts.append(coin.details['_'])
            if coin.id_bytes in self.witness:
                scripts.append(self.witness[coin.id_bytes])
            scripts.append(coin.lock)
            # enforce Stamp covenants
            if coin.details:
                if '$' in coin.details:
                    scripts.append(coin.details['$'])
                else:
                    scripts.append(Txn.std_stamp_covenant())
            if not run_auth_scripts(scripts, self.runtime_cache(coin)):
                if debug:
                    print(f'witness validation failed for a lock ({debug}):')
                    print('run_auth_scripts([')
                    for s in scripts:
                        s = Script.from_bytes(s) if type(s) is bytes else s
                        print(',\t' + '\n\t'.join(s.src.split('\n')))
                    print('])')

                return False

        # handle new stamping constraints
        for coin in self.outputs:
            if coin.details:
                if 'L' not in coin.details:
                    continue
                if coin.dsh in (c.dsh for c in self.inputs if c.details):
                    continue
                if not run_auth_scripts(
                        [self.witness.get(coin.id_bytes, b''), coin.details['L']],
                        self.runtime_cache(coin)
                    ):
                    if debug:
                        print(f'stamp creation constraint failed validation ({debug})')
                    return False
        # all other stamp constraints must be embedded in the scripts

        return True

    def runtime_cache(self, coin: Coin):
        """Construct the tapescript runtime cache for evaluating the
            lock of a given coin within the transaction.
        """
        # counts
        i_len = len(self.inputs)
        si_len = len([1 for i in self.inputs if i.details])
        o_len = len(self.outputs)
        so_len = len([1 for o in self.outputs if o.details])

        # amounts
        i_a = [int_to_bytes(i.amount) for i in self.inputs]
        o_a = [int_to_bytes(o.amount) for o in self.outputs]

        # stamp ids
        so_det = [
            sha256(packify.pack({
                k: v for k,v in o.details.items()
                if k not in ('id', 'dsh')
            })).digest()
            for o in self.outputs
            if o.details
        ]
        si_det = [
            sha256(packify.pack({
                k: v for k,v in i.details.items()
                if k not in ('id', 'dsh')
            })).digest()
            for i in self.inputs
            if i.details
        ]
        ii_det = sha256(packify.pack({
            k: v for k,v in coin.details.items()
            if k not in ('id', 'dsh')
        })).digest()

        # stamp nonces/numbers/notes
        so_n = [o.details.get('n', b'') for o in self.outputs if o.details]
        si_n = [i.details.get('n', b'') for i in self.inputs if i.details]
        ii_n = coin.details.get('n', b'')

        # stamp data-script-hashes
        so_dsh = [
            o.dsh
            for o in self.outputs
            if o.details
        ]
        si_dsh = [
            i.dsh
            for i in self.inputs
            if i.details
        ]
        ii_dsh = coin.dsh

        cache = {
            "i_len": i_len,
            "i_a": i_a,
            "si_len": si_len,
            "si_det": si_det,
            "ii_det": ii_det,
            "si_dsh": si_dsh,
            "ii_dsh": ii_dsh,
            "si_n": si_n,
            "ii_n": ii_n,
            "o_len": o_len,
            "o_a": o_a,
            "so_len": so_len,
            "so_det": so_det,
            "so_dsh": so_dsh,
            "so_n": so_n,
            "sigfield1": b'Txn',
            "sigfield2": coin.id_bytes,
            "sigfield3": sha256(
                b''.join(sorted([
                    bytes.fromhex(i) for i in self.input_ids
                ]))
            ).digest(),
            "sigfield4": sha256(
                b''.join(sorted([
                    bytes.fromhex(o) for o in self.output_ids
                ]))
            ).digest(),
        }
        return cache

    @staticmethod
    def std_stamp_covenant() -> Script:
        """Returns the standard covenant ('$' script) for unique stamps.
            This requires that there is only one stamped output and that
            it shares the same stamp ID.
        """
        return Script.from_src('''
            get_value s"so_len" push d1 equal_verify
            get_value s"so_det" get_value s"ii_det" equal_verify
        ''')

    @staticmethod
    def std_series_covenant(allow_negatives: bool = True) -> Script:
        """Returns the standard covenant ('$' script) for fungible stamps
            in a series. This requires that all stamped inputs and
            outputs share the same data-script-hash, and that the sum
            of output 'n' values is less than or equal to the sum of the
            input 'n' values. If `allow_negatives` is set to False, then
            an additional check to make sure all `n` values are positive
            will be included. (Default setting allows negative `n`
            values.)
        """
        check = '' if allow_negatives else 'dup push d0 leq verify '
        return Script.from_src(f'''
            # set some variables #
            get_value s"si_len" @= il 1
            get_value s"ii_dsh" @= s 1
            get_value s"so_len" @= ol 1

            # ensure all stamped inputs are from the same series #
            get_value s"si_dsh"
            @il loop {{
                push d-1 add_ints d2 @= i 1
                @s equal_verify
                @i
            }} pop0

            # ensure all stamped outputs are from the same series #
            get_value s"so_dsh"
            @ol loop {{
                push d-1 add_ints d2 @= i 1
                @s equal_verify
                @i
            }} pop0

            # calculate the sum of stamped inputs #
            get_value s"si_n" push d0
            @il loop {{
                {check}push d-1 add_ints d2 @= i 1
                add_ints d2
                @i
            }} pop0

            # calculate the sum of stamped outputs #
            get_value s"so_n" push d0
            @ol loop {{
                {check}push d-1 add_ints d2 @= i 1
                add_ints d2
                @i
            }} pop0

            # ensure stamped output sum <= stamped input sum #
            leq verify
        ''')

    @staticmethod
    def std_requires_burn_mint_lock(rate: int = 1000) -> Script:
        """Returns a standard mint lock 'L' script that requires burning
            EC⁻¹ at the specified `rate` to mint the 'n' value. Raises
            `TypeError` or `ValueError` for invalid `rate`.
        """
        type_assert(type(rate) is int, 'rate must be int >0')
        value_assert(rate > 0, 'rate must be int >0')
        return Script.from_src(f'''
            # sum output EC^-1 amounts #
            get_value s"o_a" push d0
            get_value s"o_len" loop {{
                push d-1 add d2 @= i 1
                add d2 @i
            }} pop0

            # sum input EC^-1 amounts #
            get_value s"i_a" push d0
            get_value s"i_len" loop {{
                push d-1 add d2 @= i 1
                add d2 @i
            }} pop0

            # calculate burn as sum(inputs)-sum(outputs) #
            sub d2

            # divide burned amount by {rate} #
            push d{rate} swap2 div

            # sum minted n values #
            get_value s"so_n" push d0
            get_value s"so_len" loop {{
                push d-1 add d2 @= i 1
                add d2 @i
            }} pop0

            # ensure minted n amount <= burned/{rate} #
            leq
        ''')

    @staticmethod
    def std_must_balance_mint_lock():
        """Returns a standard mint lock 'L' script that requires the sum
            of all 'n' values to equal 0.
        """
        return Script.from_src('''
            # sum all n values #
            get_value s"so_n" push d0
            get_value s"so_len" loop {
                push d-1 add d2 @= i 1
                add d2 @i
            } pop0

            # require the sum is equal to 0 #
            push d0 eq
        ''')


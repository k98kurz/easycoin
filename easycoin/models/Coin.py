from __future__ import annotations
from .errors import type_assert, value_assert
from hashlib import sha256
from sqloquent import HashedModel, Default, RelatedCollection, RelatedModel
from tapehash import tapehash3, work, calculate_difficulty
from tapescript import Script
from time import time
import packify


_mint_difficulty = 200
_min_coin_mint_size = 100000
_max_stamp_size = 10 * 1024


class Coin(HashedModel):
    connection_info: str = ''
    table: str = 'coins'
    id_column: str = 'id'
    columns: tuple[str] = (
        'id', 'timestamp', 'lock', 'amount', 'details', 'nonce',
        'net_id', 'net_state', 'wallet_id', 'key_index1', 'key_index2'
    )
    columns_excluded_from_hash = ('wallet_id', 'key_index1', 'key_index2')
    id: str
    timestamp: int
    lock: bytes
    amount: int
    details: bytes|None
    nonce: int|Default[0]
    net_id: str|None
    net_state: bytes|None
    wallet_id: str|None
    key_index1: int|None
    key_index2: int|None
    origins: RelatedCollection
    spends: RelatedCollection
    wallet: RelatedModel

    @classmethod
    def commitment(cls, data: dict) -> bytes:
        return super().generate_id({
            k: v
            for k,v in data.items()
            if k not in ('net_id', 'net_state')
        })

    @classmethod
    def generate_id(cls, data: dict) -> str:
        return sha256(packify.pack([
            data.get('net_id', None),
            data.get('net_state', None),
            cls.commitment(data),
        ])).digest().hex()

    @property
    def id_bytes(self) -> bytes:
        if self.id:
            return bytes.fromhex(self.id)
        return bytes.fromhex(self.generate_id(self.data))

    @property
    def lock(self) -> Script:
        return self.data['lock']
    @lock.setter
    def lock(self, val: bytes|Script):
        if isinstance(val, bytes):
            self.data['lock'] = val
        elif isinstance(val, Script):
            self.data['lock'] = val.bytes
        else:
            raise TypeError('lock must be bytes|Script')

    @property
    def details(self) -> dict:
        if self.data.get('details', None) is None:
            return {}
        return packify.unpack(self.data['details'])
    @details.setter
    def details(self, val: dict):
        type_assert(type(val) is dict, 'details must be dict')
        val = packify.pack(val)
        value_assert(len(val) <= _max_stamp_size,
            f'serialized details exceed limit of {_max_stamp_size}')
        self.data['details'] = val

    @property
    def net_id_bytes(self) -> bytes:
        if self.net_id:
            return bytes.fromhex(self.net_id)
        return b''

    def pack(self) -> bytes:
        """Serialize to bytes."""
        return packify.pack(self.data)

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> 'Coin':
        """Deserialize from bytes."""
        return cls(packify.unpack(data, inject=inject))

    def mint_value(self) -> int:
        """Calculates the mint value of the coin (if it has one)."""
        val = tapehash3(bytes.fromhex(self.generate_id(self.data)))
        val = calculate_difficulty(val)
        if val < _mint_difficulty:
            return 0
        if (val - _mint_difficulty) * 1000 < _min_coin_mint_size:
            return 0
        return (val - _mint_difficulty) * 1000

    @classmethod
    def create(
            cls, lock: bytes|Script, amount: int, net_id: bytes|None = None,
            net_state: bytes|None = None, nonce_offset: int = 0
        ) -> Coin:
        """Creates a new coin that must be funded or mined. Raises
            `TypeError` or `ValueError` for invalid parameters.
        """
        ts = int(time())
        return cls({
            'timestamp': ts,
            'lock': lock if type(lock) is bytes else lock.bytes,
            'amount': amount,
            'nonce': nonce_offset,
            'net_id': net_id,
            'net_state': net_state,
        })

    @classmethod
    def mine(
            cls, lock: bytes|Script, amount: int = _min_coin_mint_size,
            net_id: bytes|None = None, net_state: bytes|None = None,
            nonce_offset: int = 0
        ) -> Coin:
        """Mines a coin with the `amount` of value. Raises `TypeError`
            or `ValueError` for invalid parameters.
        """
        type_assert(net_id is None or type(net_id) is str,
            'net_id must be str|None')
        type_assert(type(net_state) in (str, type(None)),
            'net_state must be bytes|None')
        value_assert(amount >= _min_coin_mint_size,
            f'amount must be >= {_min_coin_mint_size}')
        coin = cls.create(lock, amount, net_id, nonce_offset)
        # calculate mint Txn fee overhead
        overhead = len(coin.preimage(coin.data)) + 3 + 32
        difficulty = ((amount + overhead) // 1000) + _mint_difficulty
        work(coin, lambda c: bytes.fromhex(c.generate_id(c.data)), difficulty, tapehash3)
        return coin

    @classmethod
    def stamp(
            cls, lock: bytes, amount: int, n: str|bytes|int,
            optional: dict[str, str|int|bool|bytes] = {},
            net_id: bytes|None = None, net_state: bytes|None = None,
        ) -> Coin:
        """Create a Stamp."""
        coin = cls.create(lock, amount, net_id, net_state)
        details = {'n': n, **optional}
        if 'd' in details:
            type_assert(type(details['d']) is dict, 'd value must be dict')
        details['id'] = sha256(packify.pack({
            k: v for k, v in details.items()
            if k not in ('id', 'dsh')
        })).digest()
        details['dsh'] = sha256(packify.pack({
            k: v for k, v in details.items()
            if k in ('d', 'L', '_', '$')
        })).digest()
        coin.details = details
        return coin


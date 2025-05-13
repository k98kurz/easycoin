from hashlib import sha256
from sqloquent import HashedModel, Default, RelatedCollection, RelatedModel
from tapehash import tapehash3, work, calculate_difficulty
from tapescript import Script
from time import time
import packify


_mint_difficulty = 200


class Coin(HashedModel):
    connection_info: str = ''
    table: str = 'coins'
    id_column: str = 'id'
    columns: tuple[str] = (
        'id', 'timestamp', 'lock', 'amount', 'details', 'nonce',
        'net_id', 'wallet_id'
    )
    columns_excluded_from_hash = ('wallet_id',)
    id: str
    timestamp: int
    lock: bytes
    amount: int
    details: bytes|None
    nonce: int|Default[0]
    net_id: str|None
    wallet_id: str|None
    origins: RelatedCollection
    spends: RelatedCollection
    wallet: RelatedModel

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
        if self.data['details'] is None:
            return {}
        return packify.unpack(self.data['details'])
    @details.setter
    def details(self, val: dict):
        if not type(val) is dict:
            raise TypeError('details must be dict')
        self.data['details'] = packify.pack(val)

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
        return (val - _mint_difficulty) * 1000

    @classmethod
    def create(
        cls, lock: bytes|Script, amount: int, net_id: bytes|None = None
    ) -> 'Coin':
        """Creates a new coin that must be funded or mined."""
        ts = int(time())
        return cls({
            'timestamp': ts,
            'lock': lock if type(lock) is bytes else lock.bytes,
            'amount': amount,
            'nonce': 0,
            'net_id': net_id,
        })

    @classmethod
    def mine(
        cls, lock: bytes|Script, amount: int = 10000, net_id: bytes|None = None
    ) -> 'Coin':
        """Mines a coin with the `amount` of value."""
        coin = cls.create(lock, amount, net_id)
        # calculate mint Txn fee overhead
        overhead = len(coin.preimage(coin.data)) + 3 + 32
        difficulty = ((amount + overhead) // 1000) + _mint_difficulty
        work(coin, lambda c: bytes.fromhex(c.generate_id(c.data)), difficulty, tapehash3)
        return coin

    @classmethod
    def stamp(
        cls, lock: bytes, amount: int, n: str|bytes|int,
        optional: dict[str, str|int|bool|bytes] = {}
    ):
        """Create a Stamp."""
        coin = cls.create(lock, amount)
        details = {'n': n, **optional}
        details['id'] = sha256(packify.pack({
            k: v for k, v in details.items()
            if k not in ('id', 'msh')
        })).digest()
        details['msh'] = sha256(packify.pack({
            k: v for k, v in details.items()
            if k in ('m', 'L', '_', '$')
        })).digest()
        coin.details = details
        return coin



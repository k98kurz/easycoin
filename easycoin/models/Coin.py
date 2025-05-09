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
    columns: tuple[str] = ('id', 'timestamp', 'lock', 'amount', 'details', 'nonce', 'wallet_id')
    columns_excluded_from_hash = ('wallet_id',)
    id: str
    timestamp: int
    lock: bytes
    amount: int
    details: bytes|None|Default[None]
    nonce: int|Default[0]
    wallet_id: str|None
    origins: RelatedCollection
    spends: RelatedCollection
    wallet: RelatedModel

    @property
    def id_bytes(self) -> bytes:
        return bytes.fromhex(self.id)

    @property
    def lock(self) -> Script:
        return Script.from_bytes(self.data['lock'])
    @lock.setter
    def lock(self, val: bytes|Script):
        if isinstance(val, bytes):
            self.data['lock'] = val
        elif isinstance(val, Script):
            self.data['lock'] = val.bytes
        else:
            raise TypeError('lock must be bytes|Script')

    @property
    def details(self) -> dict|None:
        if self.data['details'] is None:
            return None
        return packify.unpack(self.data['details'])
    @details.setter
    def details(self, val: dict):
        if not type(val) is dict:
            raise TypeError('details must be dict')
        self.data['details'] = packify.pack(val)

    def pack(self) -> bytes:
        """Serialize to bytes."""
        return packify.pack(self.data)

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> 'Coin':
        """Deserialize from bytes."""
        return cls(packify.unpack(data, inject=inject))

    def mint_value(self) -> int:
        """Calculates the mint value of the coin (if it has one)."""
        val = tapehash3(self.preimage(self.data))
        val = calculate_difficulty(val)
        if val < _mint_difficulty:
            return 0
        return (val - _mint_difficulty) * 1000

    @classmethod
    def create(cls, lock: bytes|Script, amount: int) -> 'Coin':
        """Creates a new coin that must be funded or mined."""
        ts = int(time())
        return cls({
            'timestamp': ts,
            'lock': lock if type(lock) is bytes else lock.bytes,
            'amount': amount,
            'nonce': 0,
        })

    @classmethod
    def mine(cls, lock: bytes, amount: int = 10000) -> 'Coin':
        """Mines a coin with the `amount` of value."""
        difficulty = (amount // 1000) + _mint_difficulty
        coin = cls.create(lock, amount)
        work(coin, lambda c: c.preimage(c.data), difficulty, tapehash3)
        return coin

    @classmethod
    def stamp(
        cls, lock: bytes, amount: int, n: str|bytes|int,
        optional: dict[str, str|int|bool|bytes] = {}
    ):
        """Create a Stamp."""
        coin = cls.create(lock, amount)
        details = {'n': n, **optional}
        if 'id' in details:
            del details['id']
        details['id'] = sha256(packify.pack(details)).digest()
        coin.details = details
        return coin


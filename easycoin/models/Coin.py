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
    columns: tuple[str] = ('id', 'timestamp', 'lock', 'amount', 'nonce', 'wallet_id')
    columns_excluded_from_hash = ('wallet_id',)
    id: str
    timestamp: int
    lock: bytes
    amount: int
    nonce: int|Default[0]
    wallet_id: str|None
    origins: RelatedCollection
    spends: RelatedCollection
    wallet: RelatedModel

    @property
    def lock(self) -> Script:
        return Script.from_bytes(self.data['lock'])
    @lock.setter
    def lock(self, val: bytes|Script):
        if isinstance(val, Script):
            self.data['lock'] = val.bytes
        self.data['lock']

    def pack(self) -> bytes:
        """Serialize to bytes."""
        return packify.pack(self.data)

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> 'Coin':
        """Deserialize from bytes."""
        return cls(**packify.unpack(data, inject=inject))

    def mint_value(self) -> int:
        """Calculates the mint value of the coin (if it has one)."""
        val = tapehash3(self.preimage(self.data))
        val = calculate_difficulty(val)
        if val < _mint_difficulty:
            return 0
        return (val - _mint_difficulty) * 1000

    @classmethod
    def mine(cls, lock: bytes, amount: int = 10000) -> 'Coin':
        """Mines a coin with the `amount` of value."""
        difficulty = (amount // 1000) + _mint_difficulty
        ts = int(time())
        coin = cls({
            'timestamp': ts,
            'lock': lock,
            'amount': amount,
            'nonce': 0,
        })
        work(coin, lambda c: c.preimage(c.data), difficulty, tapehash3)
        return coin


from __future__ import annotations
from hashlib import sha256
from sqloquent import SqlModel, RelatedModel, RelatedCollection
from .Coin import Coin
import packify


class Input(SqlModel):
    connection_info: str = ''
    table: str = 'inputs'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'net_id', 'net_state', 'commitment', 'wallet_id')
    id: str
    net_id: str|None
    net_state: bytes|None
    commitment: str|None
    wallet_id: str|None
    coin: RelatedModel
    trustnet: RelatedModel
    attestations: RelatedCollection
    confirmations: RelatedCollection

    @property
    def id_bytes(self) -> bytes:
        """Return the `id` as bytes (converts hexadecimal id)."""
        return bytes.fromhex(self.id)

    @property
    def net_id_bytes(self) -> bytes:
        """Return the `net_id` as bytes (converts hexadecimal id)."""
        return bytes.fromhex(self.net_id) if self.net_id else b''

    @classmethod
    def from_coin(cls, coin: Coin) -> Input:
        """Prepare an Input from a Coin, copying all necessary values."""
        return cls({
            'id': coin.id,
            'wallet_id': coin.wallet_id,
            'net_id': coin.net_id,
            'net_state': coin.net_state,
            'commitment': coin.commitment(coin.data),
        })

    def check(self) -> bool:
        """Check that the Input ID is the sha256 of the `net_id`,
            `net_state`, and `commitment`. Intended to be used for
            verification during pruning.
        """
        return sha256(packify.pack([
            self.net_id,
            self.net_state,
            self.commitment,
        ])).digest().hex() == self.id

    def pack(self) -> bytes:
        """Serialize to bytes."""
        return packify.pack([
            self.id_bytes,
            self.net_id_bytes,
            self.net_state,
            self.commitment,
        ])

    def pack_compact(self) -> bytes:
        """Serialize to bytes in compact form (no `net_id`)."""
        return packify.pack((
            self.id_bytes,
            self.net_state,
            self.commitment,
        ))

    @classmethod
    def unpack(
            cls, data: bytes, net_id: str|None = None, inject: dict = {}
        ) -> Input:
        """Deserialize from bytes. Raises ValueError or TypeError for
            invalid arguments or unpackable bytes. If the serialization
            format was compact, the provided `net_id` (or None) will be
            used.
        """
        unpacked = packify.unpack(data, inject=inject)
        if len(unpacked) == 3:
            id_bytes, net_state, commitment = unpacked
        else:
            id_bytes, net_id_bytes, net_state, commitment = unpacked
            net_id = net_id_bytes.hex()
        return cls({
            'id': id_bytes.hex(),
            'net_id': net_id,
            'net_state': net_state,
            'commitment': commitment,
        })


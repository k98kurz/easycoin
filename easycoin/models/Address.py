from __future__ import annotations
from hashlib import sha256
from sqloquent import SqlModel, RelatedModel, SqlQueryBuilder, Default
from tapescript import Script
from easycoin.models import Coin
from easycoin.models.errors import type_assert, value_assert
import packify


class Address(SqlModel):
    connection_info: str = ''
    table: str = 'addresses'
    id_column: str = 'id'
    columns: tuple[str] = (
        'id', 'lock', 'committed_script', 'secrets', 'nonce', 'child_nonce',
        'wallet_id', 'imported',
    )
    id: str
    lock: bytes
    committed_script: bytes|None
    secrets: bytes|None
    nonce: int
    child_nonce: int|None
    wallet_id: str
    imported: bool|Default[False]
    wallet: RelatedModel

    @property
    def hex(self) -> str:
        """Somewhat human-readable address representation of the lock.
            The result includes a 4-byte checksum to detect errors.
        """
        checksum = sha256(self.lock).digest()[:4]
        return (self.lock + checksum).hex()

    def coins(self) -> SqlQueryBuilder:
        """Returns a query builder for the coins associated with this address."""
        return Coin.query().equal('lock', self.lock)

    def pack(self, *, include_wallet_info: bool = False) -> bytes:
        return packify.pack({
            'lock': self.lock,
            'committed_script': self.committed_script,
            **({
                'nonce': self.nonce,
                'child_nonce': self.child_nonce,
                'wallet_id': self.wallet_id,
            } if include_wallet_info else {})
        })

    @classmethod
    def unpack(cls, data: bytes) -> Address:
        return cls(packify.unpack(data))

    @staticmethod
    def validate(address: str) -> bool:
        """Validate a hex representation of an `Address`. Returns
            `False` if the checksum check fails or if the script cannot
            be decompiled. Raises `TypeError` if the address is not a
            `str`.
        """
        type_assert(type(address) is str, 'address must be str')
        try:
            address = bytes.fromhex(address)
            lock = address[:-4]
            checksum = address[-4:]
            Script.from_bytes(lock)
            return sha256(lock).digest()[:4] == checksum
        except:
            return False

    @staticmethod
    def parse(address: str) -> bytes:
        """Parses an address into the lock bytes. Raises `TypeError` if
            address is not a `str`. Raises `ValueError` if validation
            fails.
        """
        type_assert(type(address) is str, 'address must be str')
        value_assert(Address.validate(address),
            'cannot parse an invalid address')
        return bytes.fromhex(address)[:-4]

from hashlib import sha256
from nacl.signing import SigningKey
from sqloquent import HashedModel, Default, RelatedCollection
from tapehash import tapehash3
from tapescript import (
    Script,
    make_single_sig_lock,
    make_single_sig_witness,
    make_single_sig_lock2,
    make_single_sig_witness2,
    make_multisig_lock,
    make_taproot_lock,
    make_taproot_witness_keyspend,
    make_taproot_witness_scriptspend,
    xor,
)


class Wallet(HashedModel):
    """Hierarchical deterministic wallet. Does not even attempt to
        comply with crypto industry standards, but the functionality
        is conceptually identical. After unlocking the wallet with the
        correct password
    """
    connection_info: str = ''
    table: str = 'wallets'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'seed', 'checksum', 'nonce')
    columns_excluded_from_hash = ('nonce',)
    id: str
    seed: bytes
    seed_phrase: str|None
    nonce: int|Default[0]
    txns: RelatedCollection
    coins: RelatedCollection

    @classmethod
    def create(cls, seed_phrase: str, password: str) -> 'Wallet':
        ...

    @property
    def is_locked(self) -> bool:
        return getattr(self, '_is_locked', True)

    def unlock(self, password: str):
        if not self.is_locked:
            return

        key = tapehash3(password.encode() + b'easycoin')
        for i in range(1000):
            key = tapehash3(key + i.to_bytes(2, 'big'))
        if sha256(key + b'checksum check').digest() != self.checksum:
            raise ValueError('checksum check failed; invalid password or corrupt wallet data')
        self._key = key
        self._is_locked = False

    @property
    def seed(self) -> bytes:
        if self.is_locked:
            raise TypeError('cannot read the seed from a locked wallet')
        return xor(self._key, self.data['seed'])
    @seed.setter
    def self(self, val: str):
        if self.is_locked:
            raise TypeError('cannot set the seed of a locked wallet')
        self.data['seed'] = xor(self._key, val)

    def get_seed(self, nonce: int) -> bytes:
        return sha256(self.seed + nonce.to_bytes(32, 'big')).digest()

    def p2pk(self, nonce: int) -> Script:
        seed = self.get_seed(nonce)
        skey = SigningKey(seed)
        return make_single_sig_lock(skey.verify_key)

    def p2pkh(self, nonce: int) -> Script:
        seed = self.get_seed(nonce)
        skey = SigningKey(seed)
        return make_single_sig_lock2(skey.verify_key)

    def p2tr(self, nonce: int, script: Script|None = None) -> Script:
        if not script:
            script = Script.from_src(f'push d{nonce} false return')
        seed = self.get_seed(nonce)
        skey = SigningKey(seed)
        return make_taproot_lock(skey.verify_key, script)


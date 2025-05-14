from hashlib import sha256, pbkdf2_hmac
from nacl.bindings import crypto_core_ed25519_scalar_mul, crypto_scalarmult_ed25519
from nacl.signing import SigningKey, VerifyKey
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
    clamp_scalar,
    xor,
)
import os
import packify


_empty_dict = packify.pack({})


class Wallet(HashedModel):
    """Hierarchical deterministic wallet. Does not even attempt to
        comply with crypto industry standards, but the functionality
        is conceptually identical. After unlocking the wallet with the
        correct password
    """
    connection_info: str = ''
    table: str = 'wallets'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'seed', 'checksum', 'nonce', 'pubkeys', 'secrets')
    columns_excluded_from_hash = ('nonce', 'pubkeys', 'secrets')
    id: str
    seed: bytes
    checksum: bytes
    nonce: int|Default[0]
    pubkeys: bytes|None
    txns: RelatedCollection
    coins: RelatedCollection
    inputs: RelatedCollection
    outputs: RelatedCollection

    @property
    def pubkeys(self) -> dict[tuple[int, int|None], bytes]:
        """Dict mapping (nonce, child_nonce) to bytes(VerifyKey).
            Serialized by packify for ease of database persistence.
        """
        return packify.unpack(self.data.get('pubkeys', _empty_dict))
    @pubkeys.setter
    def pubkeys(self, val: dict[tuple[int, int|None], bytes]):
        if not isinstance(val, dict):
            raise TypeError('pubkeys must be dict[tuple[int, int|None], bytes]')
        for k, v in val.items():
            if not isinstance(k, tuple) or not isinstance(v, bytes):
                raise TypeError('pubkeys must be dict[tuple[int, int|None], bytes]')
            if not len(k) == 2:
                raise ValueError('pubkeys must be dict[tuple[int, int|None], bytes]')
            if not isinstance(k[0], int) or type(k[1]) not in (int, type(None)):
                raise TypeError('pubkeys must be dict[tuple[int, int|None], bytes]')
        self.data['pubkeys'] = packify.pack(val)

    @property
    def secrets(self) -> dict[bytes, bytes]:
        """Dict mapping locks to secrets necessary for opening them.
            Intended for use with adapter signatures and HTLCs.
        """
        return packify.unpack(self.data.get('secrets', _empty_dict))
    @secrets.setter
    def secrets(self, val: dict[bytes, bytes]):
        if not isinstance(val, dict):
            raise TypeError('secrets must be dict[bytes, bytes]')
        for k, v in val.items():
            if not isinstance(k, bytes) or not isinstance(v, bytes):
                raise TypeError('secrets must be dict[bytes, bytes]')
        self.data['secrets'] = packify.pack(val)

    @property
    def is_locked(self) -> bool:
        return getattr(self, '_is_locked', True)

    def unlock(self, password: str):
        """Unlocking a wallet is done by deriving a key from the
            password via pbkdf2_hmac(sha256, 10000) and using it to
            decrypt the wallet seed. If the salted sha256 hash of the
            derived key does not match the checksum, ValueError is
            raised instead.
        """
        if not self.is_locked:
            return

        key = pbkdf2_hmac(
            'sha256', password.encode(), sha256(b'easycoin').digest(), 10000
        )
        if sha256(key + b'checksum check').digest() != self.checksum:
            raise ValueError('checksum check failed; invalid password or corrupt wallet data')
        self._key = key
        self._is_locked = False

    def lock(self):
        """Locking the wallet involves dropping the decrypted seed from
            memory.
        """
        if hasattr(self, '_key'):
            del self._key
        self._is_locked = True

    @staticmethod
    def generate_seed_phrase(wordlist: tuple[str]) -> list[str]:
        """Generates a seed phrase from the supplied wordlist using
            `os.urandom` for randomness. Raises `TypeError` if the
            wordlist is not `tuple[str]` and `ValueError` if it is not
            2048 long.
        """
        if type(wordlist) not in (tuple, list):
            raise TypeError('wordlist must be tuple[str]')
        if not all([type(w) is str for w in wordlist]):
            raise TypeError('wordlist must be tuple[str]')
        if len(wordlist) != 2048:
            raise ValueError('wordlist must contain 2048 distinct words')

        seed = os.urandom(16)
        checksum = int.from_bytes(sha256(seed).digest(), 'big') % 2048
        seed = int.from_bytes(seed, 'big')
        phrase = []
        while len(phrase) < 11:
            seed, i = divmod(seed, 2048)
            phrase.append(wordlist[i])
        phrase.append(wordlist[checksum])
        return phrase

    @classmethod
    def create(cls, seed_phrase: list[str], password: str) -> 'Wallet':
        """Create a fresh wallet using the seed phrase protected by the
            given password. Does not save to the database.
        """
        seed = sha256(''.join(seed_phrase).encode('utf-8')).digest()
        key = pbkdf2_hmac(
            'sha256', password.encode(), sha256(b'easycoin').digest(), 10000
        )
        seed = xor(seed, key)
        checksum = sha256(key + b'checksum check').digest()
        return cls({
            'seed': seed,
            'checksum': checksum,
        })

    @staticmethod
    def make_address(lock: bytes|Script) -> str:
        """Makes a somewhat human-readable address from a lock. The
            address will include a 4-byte checksum to detect errors.
            Raises `TypeError` if the lock is not a `bytes|Script`.
        """
        if type(lock) not in (bytes, Script):
            raise TypeError('lock must be bytes|Script')
        lock = lock.bytes if type(lock) is Script else lock
        checksum = sha256(lock).digest()[:4]
        return (lock + checksum).hex()

    @staticmethod
    def validate_address(address: str) -> bool:
        """Validates an address. Returns False if the checksum check
            fails or if the script cannot be decompiled. Raises
            `TypeError` if the address is not a `str`.
        """
        if type(address) is not str:
            raise TypeError('address must be str')
        try:
            address = bytes.fromhex(address)
            lock = address[:-4]
            checksum = address[-4:]
            Script.from_bytes(lock)
            return sha256(lock).digest()[:4] == checksum
        except:
            return False

    @staticmethod
    def parse_address(address: str) -> bytes:
        """Parses an address into the lock bytes. Raises `TypeError` if
            address is not a `str`. Raises `ValueError` if validation
            fails.
        """
        if type(address) is not str:
            raise TypeError('address must be str')
        if not Wallet.validate_address(address):
            raise ValueError('cannot parse an invalid address')
        return bytes.fromhex(address)[:-4]

    @property
    def seed(self) -> bytes:
        """The root seed of the wallet. Accessing raises ValueError if
            the wallet is locked.
        """
        if self.is_locked:
            raise ValueError('cannot read the seed from a locked wallet')
        return xor(self._key, self.data['seed'])
    @seed.setter
    def self(self, val: str):
        if self.is_locked:
            raise ValueError('cannot set the seed of a locked wallet')
        self.data['seed'] = xor(self._key, val)

    def get_seed(self, nonce: int, child_nonce: int|None = None) -> bytes:
        """Derives the seed with the given nonce. If child_nonce is
            supplied, this process is done a second time (hierarchical).
        """
        seed = sha256(self.seed + nonce.to_bytes(32, 'big')).digest()
        if child_nonce is None:
            return seed
        return sha256(seed + child_nonce.to_bytes(32, 'big')).digest()

    def get_pubkey(self, nonce: int, child_nonce: int|None = None) -> VerifyKey:
        """Retrieve or generate the pubkey for a given nonce and
            child_nonce. If the requested key has not been set in the
            pubkeys property, this will attempt to generate it, which
            will raise a ValueError if the wallet is locked; if this is
            successful, it will add the generated pubkey to the pubkeys
            dict.
        """
        if (nonce, child_nonce) in self.pubkeys:
            return VerifyKey(self.pubkeys[(nonce, child_nonce)])
        vkey = SigningKey(self.get_seed(nonce, child_nonce)).verify_key
        pubkeys = self.pubkeys
        pubkeys[(nonce, child_nonce)] = bytes(vkey)
        self.pubkeys = pubkeys
        return vkey

    def get_p2pk_lock(
        self, nonce: int, child_nonce: int|None = None, sigflags = 'fa'
    ) -> Script:
        """Generate the pay-to-pubkey lock for the given nonce and
            child_nonce. Raises ValueError if the wallet is locked and
            the necessary pubkey has not yet been generated. Default
            sigflags require committing to sigfield1 (input hash) and
            sigfield3 (all outputs).
        """
        return make_single_sig_lock(
            self.get_pubkey(nonce, child_nonce), sigflags
        )

    def get_p2pk_witness(
        self, nonce: int, txn: 'Txn', coin: 'Coin',
        child_nonce: int|None = None, sigflags = 'fa'
    ) -> Script:
        """Generates a valid pay-to-pubkey witness for the given nonce
            and child_nonce. Raises ValueError if the wallet is locked.
            Default sigflags commit to just sigfield1 (input hash) and
            sigfield3 (all outputs).
        """
        return make_single_sig_witness(
            self.get_seed(nonce, child_nonce),
            txn.runtime_cache(coin),
            sigflags
        )

    def get_p2pkh_lock(
        self, nonce: int, child_nonce: int|None = None, sigflags = 'fa'
    ) -> Script:
        """Generate the pay-to-pubkey-hash lock for the given nonce and
            child_nonce. Raises ValueError if the wallet is locked and
            the necessary pubkey has not yet been generated. Default
            sigflags require committing to sigfield1 (input hash) and
            sigfield3 (all outputs).
        """
        return make_single_sig_lock2(
            self.get_pubkey(nonce, child_nonce), sigflags
        )

    def get_p2pkh_witness(
        self, nonce: int, txn: 'Txn', coin: 'Coin',
        child_nonce: int|None = None, sigflags = 'fa'
    ) -> Script:
        """Generates a valid pay-to-pubkey-hash witness for the given
            nonce and child_nonce. Raises ValueError if the wallet is
            locked. Default sigflags commit to just sigfield1 (input
            hash) and sigfield3 (all outputs).
        """
        return make_single_sig_witness2(
            self.get_seed(nonce, child_nonce),
            txn.runtime_cache(coin),
            sigflags
        )

    def get_p2tr_lock(
        self, nonce: int, script: Script|None = None,
        child_nonce: int|None = None, sigflags = 'fa'
    ) -> Script:
        """Generate the pay-to-taproot lock for the given nonce and
            child_nonce. If script is not supplied, an unspendable
            locking script is generated, which will allow only the
            keyspend witness path. Raises ValueError if the wallet is
            locked and the necessary pubkey has not yet been generated.
            Default sigflags require committing to sigfield1 (input
            hash) and sigfield3 (hash of all output hashes).
        """
        if not script:
            script = Script.from_src(f'push d{nonce} false return')
        return make_taproot_lock(
            self.get_pubkey(nonce, child_nonce), script=script, sigflags=sigflags
        )

    def get_p2tr_witness_keyspend(
        self, nonce: int, txn: 'Txn', coin: 'Coin', script: Script|None = None,
        child_nonce: int|None = None, sigflags = 'fa'
    ) -> Script:
        """Generate the pay-to-taproot keyspend witness for the given
            nonce and child_nonce. If script is not supplied, an
            unspendable locking script is generated and used instead.
            Raises ValueError if the wallet is locked. Default sigflags
            commit to just sigfield1 (input hash) and sigfield3 (hash of
            all output hashes).
        """
        if not script:
            script = Script.from_src(f'push d{nonce} false return')
        return make_taproot_witness_keyspend(
            self.get_seed(nonce, child_nonce),
            txn.runtime_cache(coin),
            committed_script=script,
            sigflags=sigflags
        )

    def get_p2tr_witness_scriptspend(
        self, nonce: int, script: Script,
        child_nonce: int|None = None
    ) -> Script:
        """Generate the pay-to-taproot keyspend witness for the given
            nonce and child_nonce. Raises ValueError if the wallet is
            locked. Default sigflags commit to just sigfield1 (input
            hash) and sigfield3 (all outputs). Note that any constraints
            within the committed script must be satisfied externally to
            this method call -- this only unlocks the scriptspend path.
        """
        return make_taproot_witness_scriptspend(
            self.get_pubkey(nonce, child_nonce),
            script
        )


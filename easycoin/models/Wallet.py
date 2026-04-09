from __future__ import annotations
from easycoin.errors import type_assert, value_assert
from .Address import Address
from hashlib import sha256, pbkdf2_hmac
from nacl.bindings import crypto_core_ed25519_scalar_mul, crypto_scalarmult_ed25519
from nacl.signing import SigningKey, VerifyKey
from netaio.crypto import seal, unseal
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
    make_graftroot_lock,
    make_graftroot_witness_keyspend,
    make_graftroot_witness_surrogate,
    make_graftap_lock,
    make_graftap_witness_keyspend,
    make_graftap_witness_scriptspend,
    clamp_scalar,
)
from tapescript.tools import _make_graftap_committed_script
import os
import packify
import struct


_empty_dict = packify.pack({})


class Wallet(HashedModel):
    """Hierarchical deterministic wallet. Does not even attempt to
        comply with crypto industry standards, but the functionality
        is conceptually identical. After unlocking the wallet with the
        correct password, various types of locks and witnesses can be
        generated.
    """
    connection_info: str = ''
    table: str = 'wallets'
    id_column: str = 'id'
    columns: tuple[str] = (
        'id', 'name', 'seed', 'checksum', 'nonce', 'pubkeys', 'secrets', 'tags'
    )
    columns_excluded_from_hash = ('name', 'nonce', 'pubkeys', 'secrets', 'tags')
    id: str
    name: str
    seed: bytes
    checksum: bytes
    nonce: int|Default[0]
    pubkeys: bytes|None
    tags: str|None
    txns: RelatedCollection
    coins: RelatedCollection
    addresses: RelatedCollection
    inputs: RelatedCollection
    outputs: RelatedCollection

    @property
    def pubkeys(self) -> dict[tuple[int, int|None], bytes]:
        """Dict mapping (nonce, child_nonce) to bytes(VerifyKey).
            Serialized by packify for ease of database persistence.
        """
        return packify.unpack(self.data.get('pubkeys', None) or _empty_dict)
    @pubkeys.setter
    def pubkeys(self, val: dict[tuple[int, int|None], bytes]):
        type_assert(isinstance(val, dict),
            'pubkeys must be dict[tuple[int, int|None], bytes]')
        for k, v in val.items():
            type_assert(isinstance(k, tuple) or isinstance(v, bytes),
                'pubkeys must be dict[tuple[int, int|None], bytes]')
            value_assert(len(k) == 2,
                'pubkeys must be dict[tuple[int, int|None], bytes]')
            type_assert(isinstance(k[0], int) or type(k[1]) in (int, type(None)),
                'pubkeys must be dict[tuple[int, int|None], bytes]')
        self.data['pubkeys'] = packify.pack(val)

    @property
    def secrets(self) -> dict[bytes, bytes]:
        """Dict mapping locks to secrets necessary for opening them.
            Intended for use with adapter signatures and HTLCs.
        """
        return packify.unpack(self.data.get('secrets', None) or _empty_dict)
    @secrets.setter
    def secrets(self, val: dict[bytes, bytes]):
        type_assert(isinstance(val, dict), 'secrets must be dict[bytes, bytes]')
        for k, v in val.items():
            type_assert(isinstance(k, bytes) or isinstance(v, bytes),
                'secrets must be dict[bytes, bytes]')
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
        value_assert(sha256(key + b'checksum check').digest() == self.checksum,
            'checksum check failed; invalid password or corrupt wallet data')
        self._key = key
        self._is_locked = False

    def lock(self):
        """Locking the wallet involves dropping the decrypted seed from
            memory.
        """
        if hasattr(self, '_key'):
            del self._key
        self._is_locked = True

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt the data with the unlocked wallet's key and the seal
            function from netaio.crypto. Raises `ValueError` if the
            wallet is locked.
        """
        value_assert(not self.is_locked, 'cannot encrypt with locked wallet')
        return seal(self._key, data)

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt the data with the unlocked wallet's key and the
            unseal function from netaio.crypto. Raises `ValueError` if
            the wallet is locked.
        """
        value_assert(not self.is_locked, 'cannot decrypt with locked wallet')
        return unseal(self._key, data)

    @staticmethod
    def generate_seed_phrase(wordlist: tuple[str]) -> list[str]:
        """Generates a seed phrase from the supplied wordlist using
            `os.urandom` for randomness. Raises `TypeError` if the
            wordlist is not `tuple[str]` and `ValueError` if it is not
            2048 long.
        """
        type_assert(type(wordlist) in (tuple, list), 'wordlist must be tuple[str]')
        type_assert(all([type(w) is str for w in wordlist]),
            'wordlist must be tuple[str]')
        value_assert(len(wordlist) == 2048,
            'wordlist must contain 2048 distinct words')

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
    def create(
            cls, seed_phrase: list[str], password: str, name: str = ''
        ) -> Wallet:
        """Create a fresh wallet using the seed phrase protected by the
            given password. Does not save to the database.
        """
        seed = sha256(''.join(seed_phrase).encode('utf-8')).digest()
        key = pbkdf2_hmac(
            'sha256', password.encode(), sha256(b'easycoin').digest(), 10000
        )
        seed = seal(key, seed)
        checksum = sha256(key + b'checksum check').digest()
        return cls({
            'seed': seed,
            'checksum': checksum,
            'name': name,
        })

    def make_address(
            self, lock: bytes|Script, nonce: int, *,
            committed_script: bytes|Script|None = None,
            secrets: dict|None = None,
        ) -> Address:
        """Creates an `Address` for this wallet, but does not persist to
            the database. Raises `TypeError` for invalid parameters.
        """
        type_assert(type(lock) in (bytes, Script),
            f'lock must be bytes|Script; not {type(lock)}')
        type_assert(type(nonce) is int, 'nonce must be int')
        type_assert(type(committed_script) in (bytes, Script, type(None)),
            'committed_script must be bytes|Script|None; '
            f'not {type(committed_script)}')
        if not secrets:
            secrets = {}
        type_assert(type(secrets) is dict,
            f'secrets must be dict|None; not {type(secrets)}')
        lock = lock.bytes if type(lock) is Script else lock
        if type(committed_script) is Script:
            committed_script = committed_script.bytes
        address = Address()
        address.lock = lock
        address.nonce = nonce
        address.committed_script = committed_script
        address.secrets = self.encrypt(packify.pack(secrets))
        address.wallet_id = self.id
        return address

    def export_address(self, address: Address, *, password: str = '') -> bytes:
        """Exports an address in a way that is portable between wallets.
            Decrypts secrets with wallet key and optionally reencrypts
            with the given password. Raises `ValueError` if wallet is
            locked or if the address secrets could not be decrypted.
            Raises `TypeError` for invalid parameter types.
        """
        type_assert(isinstance(address, Address),
            f'address must be Address, not {type(address)}')
        type_assert(type(password) is str,
            f'password must be str, not {type(password)}')
        secrets = self.decrypt(address.secrets) if address.secrets else ''
        if password:
            key = pbkdf2_hmac(
                'sha256', password.encode(), sha256(b'easycoin').digest(), 10000
            )
            secrets = seal(key, secrets)
        return packify.pack({
            'data': address.pack(),
            'secrets': secrets
        })

    def import_address(self, data: bytes, *, password: str = '') -> Address:
        """Imports an address that had been previously exported. If a
            password is supplied, any secrets included in the serialized
            address will be decrypted first. Raises `ValueError` or
            `struct.error` if a password is required and not supplied, or
            if the serialized data is corrupted.
        """
        address = packify.unpack(data)
        value_assert(type(address) is dict,
            f'invalid address format: must unpack into dict, not {type(address)}')
        value_assert('data' in address,
            'invalid address format: unpacked dict missing data')
        value_assert('secrets' in address,
            'invalid address format: unpacked dict missing secrets')
        secrets = address['secrets']
        if password:
            key = pbkdf2_hmac(
                'sha256', password.encode(), sha256(b'easycoin').digest(), 10000
            )
            secrets = unseal(key, secrets)
        try:
            value_assert(type(packify.unpack(secrets)) is dict,
                'invalid address format: secrets must unpack into dict, '
                f'not {type(secrets)}'
            )
        except struct.error:
            raise ValueError(
                'invalid address format: secrets must unpack into dict; '
                'missing password?'
            )
        secrets = self.encrypt(secrets)
        addr = Address.unpack(address['data'])
        addr.wallet_id = self.id
        addr.secrets = secrets
        return addr

    @staticmethod
    def get_lock_type(
            lock: Script | bytes, address_secrets: dict | None = None
        ) -> str:
        """Get lock type string from lock bytes."""
        # ensure it is compiled and decompiled
        if isinstance(lock, Script):
            lock = lock.bytes
        lock = Script.from_bytes(lock)
        address_secrets = address_secrets or {}

        tokens = lock.src.split()

        if  (   len(tokens) == 5
                and tokens[:2] == ['OP_PUSH1', 'd32']
                and tokens[3] == 'OP_CHECK_SIG'
            ):
            return "P2PK" # public key
        elif (  len(tokens) == 9
                and tokens[:2] == ['OP_DUP', 'OP_SHAKE256']
                and tokens[-3:-1] == ['OP_EQUAL_VERIFY', 'OP_CHECK_SIG']
            ):
            return "P2PKH" # public key hash
        elif (  len(tokens) == 5
                and tokens[:2] == ['OP_PUSH1', 'd32']
                and tokens[-2] == 'OP_TAPROOT'
            ):
            if address_secrets and "P2GT" in address_secrets:
                return "P2GT" # graftap: graftroot-in-taproot
            return "P2TR" # taproot
        elif (  len(tokens) == 8
                and tokens[:2] == ['OP_DUP', 'OP_SHAKE256']
                and tokens[-2:] == ['OP_EQUAL_VERIFY', 'OP_EVAL']
            ):
            return "P2SH" # script hash
        elif (  len(tokens) == 25
                and tokens[:2] == ['OP_PUSH1', 'd32']
                and tokens[3:23] == [
                    'OP_WRITE_CACHE', 'x6b', 'd1', 'OP_IF', '{', 'OP_DUP', 'OP_SWAP',
                    'd1', 'd2', 'OP_READ_CACHE', 'x6b', 'OP_CHECK_SIG_STACK',
                    'OP_VERIFY', 'OP_EVAL', '}', 'ELSE', '{', 'OP_READ_CACHE', 'x6b',
                    'OP_CHECK_SIG'
                ]
            ):
            return "P2GR" # graftroot
        elif (  len(tokens) >= 8
                and 'OP_PUSH1' in tokens
                and 'OP_CHECK_MULTISIG' in tokens
            ):
            return "MultiSig"
        else:
            return "Unknown"

    @property
    def seed(self) -> bytes:
        """The root seed of the wallet. Accessing raises ValueError if
            the wallet is locked.
        """
        value_assert(not self.is_locked,
            'cannot read the seed from a locked wallet')
        return self.decrypt(self.data['seed'])
    @seed.setter
    def seed(self, val: str):
        value_assert(not self.is_locked,
            'cannot set the seed of a locked wallet')
        self.data['seed'] = self.encrypt(val)

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
        self.save()
        return vkey

    def get_p2pk_lock(
            self, nonce: int, child_nonce: int|None = None, sigflags: str = 'f4'
        ) -> Script:
        """Generate the pay-to-pubkey lock for the given `nonce` and
            `child_nonce`. Raises `ValueError` if the wallet is locked
            and the necessary pubkey has not yet been generated. Default
            sigflags require signing sigfield1 (signature scope),
            sigfield2 (coin hash), and sigfield4 (all outputs); i.e.
            sigfield{3,5,6,7,8} can be left unsigned.
        """
        return make_single_sig_lock(
            self.get_pubkey(nonce, child_nonce), sigflags
        )

    def get_p2pk_witness(
            self, nonce: int, txn: 'Txn', coin: 'Coin',
            child_nonce: int|None = None, sigflags = '00'
        ) -> Script:
        """Generates a valid pay-to-pubkey witness for the given `nonce`
            and `child_nonce`. Raises `ValueError` if the wallet is
            locked. Default sigflags sign all sigfields.
        """
        return make_single_sig_witness(
            self.get_seed(nonce, child_nonce),
            txn.runtime_cache(coin),
            sigflags
        )

    def get_p2pkh_lock(
            self, nonce: int, child_nonce: int|None = None, sigflags = 'f4'
        ) -> Script:
        """Generate the pay-to-pubkey-hash lock for the given `nonce`
            and `child_nonce`. Raises `ValueError` if the wallet is
            locked and the necessary pubkey has not yet been generated.
            Default sigflags require signing sigfield1 (signature
            scope), sigfield2 (coin hash), and sigfield4 (all outputs);
            i.e. sigfield{3,5,6,7,8} can be left unsigned.
        """
        return make_single_sig_lock2(
            self.get_pubkey(nonce, child_nonce), sigflags
        )

    def get_p2pkh_witness(
            self, nonce: int, txn: 'Txn', coin: 'Coin',
            child_nonce: int|None = None, sigflags = '00'
        ) -> Script:
        """Generates a valid pay-to-pubkey-hash witness for the given
            `nonce` and `child_nonce`. Raises `ValueError` if the wallet
            is locked. Default sigflags sign all sigfields.
        """
        return make_single_sig_witness2(
            self.get_seed(nonce, child_nonce),
            txn.runtime_cache(coin),
            sigflags
        )

    def get_p2tr_lock(
            self, nonce: int, script: Script|None = None,
            child_nonce: int|None = None, sigflags = 'f4'
        ) -> Script:
        """Generate the pay-to-taproot lock for the given `nonce` and
            `child_nonce`. If script is not supplied, an unspendable
            locking script is generated, which will allow only the
            keyspend witness path. Raises `ValueError` if the wallet is
            locked and the necessary pubkey has not yet been generated.
            Default sigflags require signing sigfield1 (signature
            scope), sigfield2 (coin hash), and sigfield4 (hash of all
            output hashes); i.e. sigfield{3,5,6,7,8} can be left
            unsigned.
        """
        if not script:
            script = Script.from_src(f'push d{nonce} false return')
        return make_taproot_lock(
            self.get_pubkey(nonce, child_nonce), script=script, sigflags=sigflags
        )

    def get_p2tr_witness_keyspend(
            self, nonce: int, txn: 'Txn', coin: 'Coin', script: Script|None = None,
            child_nonce: int|None = None, sigflags = '00'
        ) -> Script:
        """Generate the pay-to-taproot keyspend witness for the given
            `nonce` and `child_nonce`. If script is not supplied, an
            unspendable locking script is generated and used instead.
            Raises `ValueError` if the wallet is locked. Default
            sigflags sign all sigfields. Default sigflags sign all
            sigfields.
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
            `nonce` and `child_nonce`. Raises `ValueError` if the wallet
            is locked. Note that any constraints within the committed
            script must be satisfied externally to this method call --
            this only unlocks the scriptspend path.
        """
        return make_taproot_witness_scriptspend(
            self.get_pubkey(nonce, child_nonce),
            script
        )

    def get_p2gr_lock(
            self, nonce: int, child_nonce: int|None = None, sigflags: str = 'f4'
        ) -> Script:
        """Generate the pay-to-graftroot lock for the given `nonce` and
            `child_nonce`. Can be unlocked with a keyspend or surrogate
            script path. Raises `ValueError` if the wallet is locked and
            the necessary pubkey has not yet been generated. Default
            sigflags require signing sigfield1 (signature scope),
            sigfield2 (coin hash), and sigfield4 (all outputs); i.e.
            sigfield{3,5,6,7,8} can be left unsigned.
        """
        return make_graftroot_lock(
            self.get_pubkey(nonce, child_nonce), sigflags=sigflags
        )

    def get_p2gr_witness_keyspend(
            self, nonce: int, txn: 'Txn', coin: 'Coin',
            child_nonce: int|None = None, sigflags: str = '00'
        ) -> Script:
        """Generate the pay-to-graftroot keyspend witness for the given
            `nonce` and `child_nonce`, which is a signature and a
            boolean control signal. Raises `ValueError` if the wallet is
            locked. Default sigflags sign all sigfields.
        """
        return make_graftroot_witness_keyspend(
            self.get_seed(nonce, child_nonce),
            txn.runtime_cache(coin),
            sigflags=sigflags
        )

    def get_p2gr_witness_surrogate(
            self, nonce: int, surrogate_script: Script|str,
            child_nonce: int|None = None
        ) -> Script:
        """Generate the pay-to-graftroot surrogate script witness for
            the given `nonce` and `child_nonce`, which pushes the
            surrogate script, a signature for the surrogate script, and
            a boolean control flag. Raises `ValueError` if the wallet is
            locked. Note that any constraints within the surrogate
            script must be satisfied externally to this method call --
            this only authorizes and prepares the execution of the
            surrogate script.
        """
        return make_graftroot_witness_surrogate(
            self.get_seed(nonce, child_nonce),
            surrogate_script
        )

    def get_p2gt_lock(
            self, nonce: int, child_nonce: int|None = None
        ) -> Script:
        """Generate the pay-to-graftap (P2GR in P2TR envelope) lock for
            the given `nonce` and `child_nonce`. Unlike regular P2GR,
            the keyspend path is a regular P2TR keyspend, while the
            scriptspend path is exclusively for executing surrogate
            scripts. Raises `ValueError` if the wallet is locked and the
            necessary pubkey has not yet been generated. Note:
            tapescript v0.7.2 does not allow sigflags other than '00'
            for graftap, which means that all sigfields must be signed;
            this will be changed when fixed in the next release of
            tapescript.
        """
        return make_graftap_lock(
            self.get_pubkey(nonce, child_nonce)
        )

    def get_p2gt_committed_script(
            self, nonce: int, child_nonce: int|None = None
        ) -> Script:
        """Generate the pay-to-graftap committed script that allows
            executing a signed surrogate script via the scripspend path
            of the P2TR envelope. Raises `ValueError` if the wallet is
            locked and the necessary pubkey has not yet been generated.
        """
        return _make_graftap_committed_script(self.get_pubkey(nonce, child_nonce))

    def get_p2gt_witness_keyspend(
            self, nonce: int, txn: 'Txn', coin: 'Coin',
            child_nonce: int|None = None, sigflags: str = '00'
        ) -> Script:
        """Generate the pay-to-graftap keyspend witness for the given
            `nonce` and `child_nonce`. This is indistinguishable from
            any other P2TR keyspend witness. Raises `ValueError` if the
            wallet is locked. Default sigflags sign all sigfields.
        """
        return make_graftap_witness_keyspend(
            self.get_seed(nonce, child_nonce),
            txn.runtime_cache(coin),
            sigflags=sigflags
        )

    def get_p2gt_witness_scriptspend(
            self, nonce: int, surrogate_script: Script,
            child_nonce: int|None = None
        ) -> Script:
        """Generate the pay-to-taproot scriptspend witness for the given
            `nonce` and `child_nonce`, which supplies the committed P2GR
            script and internal pubkey to unlock the P2TR envelope's
            scriptspend path, as well as the P2GR surrogate script and
            signature. This is slightly different from raw P2GR in that
            the control boolean is excluded since keyspend is handled by
            the P2TR envelope. Raises `ValueError` if the wallet is
            locked. Note that any constraints within the surrogate
            script must be satisfied externally to this method call --
            this only authorizes and prepares the execution of the
            surrogate script via the scriptspend path of the P2TR
            envelope.
        """
        return make_graftap_witness_scriptspend(
            self.get_seed(nonce, child_nonce),
            surrogate_script
        )


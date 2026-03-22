from context import models, easycoin
from genericpath import isfile
from hashlib import sha256
from nacl.signing import VerifyKey, SigningKey
from sqlite3 import OperationalError
from tapehash import calculate_difficulty, tapehash3
from tapescript import (
    Script, run_auth_scripts, make_graftroot_lock, make_multisig_lock
)
import os
import sqloquent
import struct
import unittest



DB_FILEPATH = 'tests/test.db'
MIGRATIONS_PATH = 'tests/migrations'
SEED_PHRASE = ['test', 'obviously', 'not', 'secure']
PASSWORD = 'testp4ssword'
WALLET_NAME = 'test wallet'
ANYONE_CAN_SPEND_LOCK = Script.from_src('true')


class TestWalletAndAddress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models.set_connection_info(DB_FILEPATH)
        if isfile(DB_FILEPATH):
            os.remove(DB_FILEPATH)
        models.publish_migrations(MIGRATIONS_PATH)
        models.automigrate(MIGRATIONS_PATH, DB_FILEPATH)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        for file in os.listdir(MIGRATIONS_PATH):
            if isfile(f'{MIGRATIONS_PATH}/{file}'):
                os.remove(f'{MIGRATIONS_PATH}/{file}')
        if isfile(DB_FILEPATH):
            os.remove(DB_FILEPATH)
        super().tearDownClass()

    def setUp(self):
        for m in [
            models.Coin, models.Txn, models.Wallet, models.Address,
            models.Input, models.Output,
            models.TrustNet, models.Attestation, models.Confirmation,
            models.Snapshot, models.Chunk,
            sqloquent.DeletedModel,
        ]:
            m.query().delete()
        super().setUp()

    def test_generate_seed_phrase_returns_randomized_wordlist(self):
        phrase1 = models.Wallet.generate_seed_phrase(easycoin.wordlist())
        phrase2 = models.Wallet.generate_seed_phrase(easycoin.wordlist())
        assert type(phrase1) is type(phrase2) is list
        assert all([type(w) is str for w in phrase1])
        assert all([type(w) is str for w in phrase2])
        assert phrase1 != phrase2
        print(f'{phrase1=}')
        print(f'{phrase2=}')

    def test_create_returns_locked_Wallet(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME)
        assert type(w) is models.Wallet
        assert w.is_locked
        assert len(w.data['seed']) == 80, len(w.data['seed'])
        assert len(w.checksum) == 32

    def test_reading_seed_from_locked_Wallet_raises_ValueError(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME)
        assert w.is_locked
        with self.assertRaises(ValueError):
            w.seed

    def test_locked_Wallet_can_be_unlocked(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME)
        assert w.is_locked
        w.unlock(PASSWORD)
        assert not w.is_locked
        assert len(w.seed) == 32

    def test_lock_type_methods_e2e(self):
        wallet = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME)
        wallet.unlock(PASSWORD)
        p2pk_lock = wallet.get_p2pk_lock(1)
        p2pkh_lock = wallet.get_p2pkh_lock(1)
        p2tr_lock = wallet.get_p2tr_lock(1, script=p2pk_lock)
        p2gr_lock = make_graftroot_lock(wallet.get_pubkey(1), sigflags='fa')
        multisig_lock = make_multisig_lock(
            [wallet.get_pubkey(1), wallet.get_pubkey(2), wallet.get_pubkey(3)],
            2, sigflags='fa'
        )
        assert models.Wallet.get_lock_type(p2pk_lock) == 'P2PK', (
            models.Wallet.get_lock_type(p2pk_lock),
            Script.from_bytes(p2pk_lock.bytes).src.split())
        assert models.Wallet.get_lock_type(p2pkh_lock) == 'P2PKH', (
            models.Wallet.get_lock_type(p2pkh_lock),
            Script.from_bytes(p2pkh_lock.bytes).src.split())
        assert models.Wallet.get_lock_type(p2tr_lock) == 'P2TR', (
            models.Wallet.get_lock_type(p2tr_lock),
            Script.from_bytes(p2tr_lock.bytes).src.split())
        assert models.Wallet.get_lock_type(p2gr_lock) == 'P2GR', (
            models.Wallet.get_lock_type(p2gr_lock),
            Script.from_bytes(p2gr_lock.bytes).src.split())
        assert models.Wallet.get_lock_type(multisig_lock) == 'MultiSig', (
            models.Wallet.get_lock_type(multisig_lock),
            Script.from_bytes(multisig_lock.bytes).src.split())

    def test_get_seed_from_unlocked_Wallet_returns_new_seed(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME)
        w.unlock(PASSWORD)
        seed1 = w.get_seed(1)
        assert type(seed1) is bytes
        assert len(seed1) == 32
        assert seed1 != w.seed
        seed2 = w.get_seed(2)
        assert type(seed2) is bytes
        assert len(seed2) == 32
        assert seed2 != w.seed
        assert seed2 != seed1

        # hierarchical grandchild seed
        seed11 = w.get_seed(1, 1)
        assert type(seed11) is bytes
        assert len(seed11) == 32
        assert seed11 != w.seed
        assert seed11 != seed1

    def test_get_pubkey_from_locked_Wallet_works_after_it_is_first_generated(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME)
        with self.assertRaises(ValueError):
            w.get_pubkey(1)
        w.unlock(PASSWORD)
        pub1 = w.get_pubkey(1)
        assert type(pub1) is VerifyKey
        w.lock()
        assert w.get_pubkey(1) == pub1

    def test_get_pubkey_validates_signatures_from_same_seed(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME)
        w.unlock(PASSWORD)
        seed = w.get_seed(420, 69)
        pubk = w.get_pubkey(420, 69)
        msg = b'hello world'
        sig = SigningKey(seed).sign(msg)
        assert pubk.verify(sig)

    def test_lock_and_witness_generation_e2e(self):
        # setup
        w = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME)
        w.unlock(PASSWORD)
        hdw_i = (123, 32)
        coin = models.Coin.mine(ANYONE_CAN_SPEND_LOCK)
        coin.save()
        txn = models.Txn({'output_ids': coin.id, 'input_ids': ''})

        # p2pk
        lock = w.get_p2pk_lock(*hdw_i)
        witness = w.get_p2pk_witness(hdw_i[0], txn, coin, hdw_i[1])
        assert run_auth_scripts([witness, lock], txn.runtime_cache(coin))

        # p2pkh
        lock = w.get_p2pkh_lock(*hdw_i)
        witness = w.get_p2pkh_witness(hdw_i[0], txn, coin, hdw_i[1])
        assert run_auth_scripts([witness, lock], txn.runtime_cache(coin))

        # p2tr keyspend
        lock = w.get_p2tr_lock(hdw_i[0], child_nonce=hdw_i[1])
        witness = w.get_p2tr_witness_keyspend(hdw_i[0], txn, coin, child_nonce=hdw_i[1])
        assert run_auth_scripts([witness, lock], txn.runtime_cache(coin))

        # p2tr scriptspend
        lock = w.get_p2tr_lock(hdw_i[0], ANYONE_CAN_SPEND_LOCK, child_nonce=hdw_i[1])
        witness = w.get_p2tr_witness_scriptspend(
            hdw_i[0], ANYONE_CAN_SPEND_LOCK, child_nonce=hdw_i[1]
        )
        assert run_auth_scripts([witness, lock], txn.runtime_cache(coin))

    def test_Wallet_gen_and_pubkey_saving_e2e(self):
        phrase = models.Wallet.generate_seed_phrase(easycoin.wordlist())
        w = models.Wallet.create(phrase, PASSWORD, WALLET_NAME)
        w.unlock(PASSWORD)
        hdw_i = (420, 69)
        assert hdw_i not in w.pubkeys
        pubk = w.get_pubkey(*hdw_i)
        assert hdw_i in w.pubkeys
        w.lock()
        w.save()
        w.reload()
        assert w.get_pubkey(*hdw_i) == pubk

    def test_Wallet_relations_work(self):
        # create records
        w = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME).save()
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 999).save()
        t = models.Txn.insert({'output_ids': c.id})
        i = models.Input.insert({'id': 'some coin ID that was spent'})
        o = models.Output.insert({'id': 'some coin ID that can be spent'})

        # set relations
        c.wallet = w
        c.wallet().save()
        t.wallet = w
        t.wallet().save()
        i.wallet = w
        i.wallet().save()
        o.wallet = w
        o.wallet().save()

        # reload and test
        w.coins().reload()
        w.txns().reload()
        w.outputs().reload()
        w.inputs().reload()
        assert len(w.coins) == 1
        assert w.coins[0].id == c.id
        assert len(w.txns) == 1
        assert w.txns[0].id == t.id
        assert len(w.inputs) == 1
        assert w.inputs[0].id == i.id
        assert len(w.outputs) == 1
        assert w.outputs[0].id == o.id

    def test_Address_str_format_methods(self):
        lock = b'\x01'
        addr = models.Address({'lock': lock})
        assert type(addr.hex) is str
        assert len(addr.hex) == (len(lock) + 4) * 2, len(addr.hex)
        assert models.Address.validate(addr.hex)
        assert type(models.Address.parse(addr.hex)) is bytes, (
            type(models.Address.parse(addr.hex)))
        assert models.Address.parse(addr.hex) == lock, (
            lock, models.Address.parse(addr.hex))
        assert not models.Address.validate('12' + addr.hex)
        assert not models.Address.validate(addr.hex + '12')
        with self.assertRaises(TypeError):
            models.Address.validate(b'not a str')

    def test_Address_seialization_and_deserialization(self):
        lock = b'\x01'
        addr = models.Address({'lock': lock})
        packed1 = addr.pack()
        assert type(packed1) is bytes, type(packed1)
        unpacked = models.Address.unpack(packed1)
        assert type(unpacked) is models.Address, type(unpacked)
        assert unpacked.lock == addr.lock
        packed2 = addr.pack(include_wallet_info=True)
        assert len(packed2) > len(packed1), (packed2, packed1)

    def test_Wallet_Address_e2e(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD, WALLET_NAME)
        w.save()
        w.unlock(PASSWORD)
        lock = w.get_p2pkh_lock(w.nonce)
        address = w.make_address(lock, w.nonce, secrets={'secret': 'passcode'})
        assert type(address) is models.Address
        address.save()

        # reload from db
        w = models.Wallet.find(w.id)
        w.unlock(PASSWORD)
        address = models.Address.find(address.id)

        # test relations
        assert address.wallet and address.wallet.id == w.id
        assert w.addresses and [a.id for a in w.addresses] == [address.id]

        # export and import: with and without password
        exported1 = w.export_address(address, password=PASSWORD)
        exported2 = w.export_address(address)
        assert type(exported1) is bytes, type(exported1)
        assert type(exported2) is bytes, type(exported2)
        assert len(exported1) > len(exported2), (len(exported1), len(exported2))
        
        imported1 = w.import_address(exported1, password=PASSWORD)
        imported2 = w.import_address(exported2)
        assert type(imported1) is models.Address, type(imported1)
        assert type(imported2) is models.Address, type(imported2)

        # error handling
        with self.assertRaises(TypeError):
            w.export_address('not an address')
        with self.assertRaises(TypeError):
            w.export_address(address, password=b'not a string')
        w.lock()
        with self.assertRaises(ValueError):
            w.export_address(address) # wallet is locked
        w.unlock(PASSWORD)
        with self.assertRaises(ValueError):
            w.import_address(exported1) # missing password
        with self.assertRaises(struct.error):
            w.import_address(exported2[:-3]) # corrupted data
        with self.assertRaises(ValueError):
            w.import_address(b'akjahkjhad') # random data


if __name__ == '__main__':
    unittest.main()


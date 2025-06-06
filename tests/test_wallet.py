from context import models, easycoin
from genericpath import isfile
from hashlib import sha256
from nacl.signing import VerifyKey, SigningKey
from sqlite3 import OperationalError
from tapehash import calculate_difficulty, tapehash3
from tapescript import Script, run_auth_scripts
import os
import sqloquent
import unittest



DB_FILEPATH = 'tests/test.db'
MIGRATIONS_PATH = 'tests/migrations'
SEED_PHRASE = ['test', 'obviously', 'not', 'secure']
PASSWORD = 'testp4ssword'
ANYONE_CAN_SPEND_LOCK = Script.from_src('true')


class TestWallet(unittest.TestCase):
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
            models.Coin, models.Txn, models.Wallet, models.Input, models.Output,
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
        w = models.Wallet.create(SEED_PHRASE, PASSWORD)
        assert type(w) is models.Wallet
        assert w.is_locked
        assert len(w.data['seed']) == 32
        assert len(w.checksum) == 32

    def test_reading_seed_from_locked_Wallet_raises_ValueError(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD)
        assert w.is_locked
        with self.assertRaises(ValueError):
            w.seed

    def test_locked_Wallet_can_be_unlocked(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD)
        assert w.is_locked
        w.unlock(PASSWORD)
        assert not w.is_locked
        assert len(w.seed) == 32

    def test_address_methods_e2e(self):
        address = models.Wallet.make_address(ANYONE_CAN_SPEND_LOCK)
        assert type(address) is str
        assert models.Wallet.validate_address(address)
        lock = models.Wallet.parse_address(address)
        assert type(lock) is bytes
        assert lock == ANYONE_CAN_SPEND_LOCK.bytes
        assert not models.Wallet.validate_address(address + 'st')
        assert not models.Wallet.validate_address(address + 'ab')

    def test_get_seed_from_unlocked_Wallet_returns_new_seed(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD)
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
        w = models.Wallet.create(SEED_PHRASE, PASSWORD)
        with self.assertRaises(ValueError):
            w.get_pubkey(1)
        w.unlock(PASSWORD)
        pub1 = w.get_pubkey(1)
        assert type(pub1) is VerifyKey
        w.lock()
        assert w.get_pubkey(1) == pub1

    def test_get_pubkey_validates_signatures_from_same_seed(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD)
        w.unlock(PASSWORD)
        seed = w.get_seed(420, 69)
        pubk = w.get_pubkey(420, 69)
        msg = b'hello world'
        sig = SigningKey(seed).sign(msg)
        assert pubk.verify(sig)

    def test_lock_and_witness_generation_e2e(self):
        # setup
        w = models.Wallet.create(SEED_PHRASE, PASSWORD)
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
        w = models.Wallet.create(phrase, PASSWORD)
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
        w = models.Wallet.create(SEED_PHRASE, PASSWORD).save()
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


if __name__ == '__main__':
    unittest.main()


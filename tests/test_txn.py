from context import models
from dataclasses import dataclass, field
from genericpath import isfile
from hashlib import sha256
from nacl.signing import SigningKey
from sqlite3 import OperationalError
from tapehash import calculate_difficulty, tapehash3
from tapescript import Script, make_single_sig_lock, make_single_sig_witness
import os
import packify
import sqloquent
import unittest



DB_FILEPATH = 'tests/test.db'
MIGRATIONS_PATH = 'tests/migrations'
ANYONE_CAN_SPEND_LOCK = Script.from_src('true')
SKEY = os.urandom(32)
SINGLE_SIG_LOCK = make_single_sig_lock(SigningKey(SKEY).verify_key)


def make_hashlock(preimage: bytes):
    return Script.from_src(
        f'sha256 push x{sha256(preimage).digest().hex()} equal'
    )


class TestTxn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models.Coin.connection_info = DB_FILEPATH
        models.Txn.connection_info = DB_FILEPATH
        models.Input.connection_info = DB_FILEPATH
        models.Output.connection_info = DB_FILEPATH
        models.Wallet.connection_info = DB_FILEPATH
        sqloquent.DeletedModel.connection_info = DB_FILEPATH
        if isfile(DB_FILEPATH):
            os.remove(DB_FILEPATH)
        cls.automigrate()
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
        models.Coin.query().delete()
        models.Txn.query().delete()
        models.Input.query().delete()
        models.Output.query().delete()
        models.Wallet.query().delete()
        sqloquent.DeletedModel.query().delete()
        super().setUp()

    @classmethod
    def automigrate(self):
        sqloquent.tools.publish_migrations(MIGRATIONS_PATH)
        tomigrate = [ 
            models.Coin, models.Txn, models.Wallet,
            models.Input, models.Output,
        ]
        for model in tomigrate:
            name = model.__name__
            m = sqloquent.tools.make_migration_from_model(model, name)
            with open(f'{MIGRATIONS_PATH}/create_{name}.py', 'w') as f:
                f.write(m)
        sqloquent.tools.automigrate(MIGRATIONS_PATH, DB_FILEPATH)

    def test_details_serializes_properly(self):
        t = models.Txn()
        t.details = {'test': 123}
        assert type(t.data['details']) is bytes

    def test_details_raises_TypeError_for_invalid_data(self):
        t = models.Txn()
        with self.assertRaises(TypeError):
            t.details = "Not a dict"

    def test_witness_serializes_properly(self):
        t = models.Txn()
        t.witness = {b"1"*32: ANYONE_CAN_SPEND_LOCK.bytes}
        assert type(t.data['witness']) is bytes

    def test_witness_raises_TypeError_for_invalid_data(self):
        t = models.Txn()
        with self.assertRaises(TypeError):
            t.witness = "Not a dict"
        with self.assertRaises(TypeError):
            t.witness = {
                'not bytes': ANYONE_CAN_SPEND_LOCK.bytes,
            }
        with self.assertRaises(TypeError):
            t.witness = {
                b"some sha256 coin id": "Not bytes",
            }

    def test_witness_raises_ValueError_for_invalid_key_length(self):
        t = models.Txn()
        with self.assertRaises(ValueError):
            t.witness = {
                b"not 32 bytes": b'adf'
            }

    def test_serialization_e2e(self):
        c1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 9999)
        c1.save()
        c2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1111)
        c2.save()
        t = models.Txn()
        t.input_ids = [c1.id]
        t.inputs().reload()
        t.output_ids = [c2.id]
        t.outputs().reload()
        t.witness = {c1.id_bytes: b''}
        packed = t.pack()
        unpacked = models.Txn.unpack(packed)
        assert unpacked.generate_id(unpacked.data) == t.generate_id(t.data)
        assert len(unpacked.inputs) == len(t.inputs)
        assert len(unpacked.outputs) == len(t.outputs)
        assert c1.id_bytes in unpacked.witness

    def test_minimum_fee_returns_int_that_scales_with_witness_size(self):
        t = models.Txn({'output_ids': '', 'input_ids': ''})
        mf1 = models.Txn.minimum_fee(t)
        assert type(mf1) is int and mf1 > 0

        t.witness = {
            sha256(b"input1 id").digest(): ANYONE_CAN_SPEND_LOCK.bytes,
        }
        mf2 = models.Txn.minimum_fee(t)
        assert mf2 > mf1

        t.witness = {
            sha256(b"input1 id").digest(): ANYONE_CAN_SPEND_LOCK.bytes,
            sha256(b"input2 id").digest(): ANYONE_CAN_SPEND_LOCK.bytes,
        }
        mf3 = models.Txn.minimum_fee(t)
        assert mf3 > mf2

    def test_minimum_fee_returns_int_that_does_not_scale_with_input_count(self):
        t = models.Txn()
        mf1 = models.Txn.minimum_fee(t)
        assert type(mf1) is int and mf1 > 0

        t.input_ids = ['123']
        mf2 = models.Txn.minimum_fee(t)
        assert mf2 == mf1

        t.input_ids = ['123','321']
        mf3 = models.Txn.minimum_fee(t)
        assert mf3 == mf2

    def test_minimum_fee_returns_int_that_scales_with_output_count(self):
        t = models.Txn()
        mf1 = models.Txn.minimum_fee(t)
        assert type(mf1) is int and mf1 > 0

        t.output_ids = ['123','321']
        mf2 = models.Txn.minimum_fee(t)
        assert mf2 > mf1

        t.output_ids = ['123','321','456']
        mf3 = models.Txn.minimum_fee(t)
        assert mf3 > mf2

    def test_minimum_fee_returns_int_that_scales_with_output_len(self):
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 999)
        c.save()
        t = models.Txn({'output_ids': c.id})
        mf1 = models.Txn.minimum_fee(t)
        assert type(mf1) is int and mf1 > 0

        c = models.Coin.create(make_hashlock(b'test'), 999)
        c.save()
        t = models.Txn({'output_ids': c.id, 'input_ids': ''})
        mf2 = models.Txn.minimum_fee(t)
        assert mf2 > mf1

    def test_validate_rejects_mint_txn_that_fails_difficulty_threshold(self):
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 999999999999999)
        while c.mint_value() >= c.amount:
            c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 999999999999999)
        c.save()
        t = models.Txn({'output_ids': c.id, 'input_ids': ''})
        #print(f'1 {c.mint_value()=}, {c.amount=}')
        assert not t.validate()

    def test_validate_accepts_mint_txn_that_meets_difficulty_threshold(self):
        c = models.Coin.mine(ANYONE_CAN_SPEND_LOCK)
        c.save()
        t = models.Txn({'output_ids': c.id, 'input_ids':''})
        #print(f'2 {c.mint_value()=}, {c.amount=}')
        assert t.validate()

    def test_validate_accepts_valid_mint_and_spend(self):
        # first mine a coin and add it to the UTXO set
        c1 = models.Coin.mine(SINGLE_SIG_LOCK)
        c1.save()
        t = models.Txn({'output_ids': c1.id, 'input_ids': ''})
        assert t.validate()
        t.save()
        # now spend it
        c2 = models.Coin.create(SINGLE_SIG_LOCK, c1.amount - 500)
        c2.save()
        t = models.Txn({'input_ids': c1.id, 'output_ids': c2.id})
        t.witness = {
            c1.id_bytes: make_single_sig_witness(SKEY, t.runtime_cache(c1)).bytes
        }
        assert t.validate()

    def test_basic_stamp_creation_and_spend_validate(self):
        coin = models.Coin.mine(ANYONE_CAN_SPEND_LOCK)
        coin.save()
        s1 = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, coin.amount - 1000, b'test')
        assert s1.details['n'] == b'test'
        s1.save()
        t = models.Txn()
        t.input_ids = [coin.id]
        t.output_ids = [s1.id]
        assert t.validate()
        s2 = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, s1.amount - 1000, s1.details['n'])
        s2.save()
        t = models.Txn()
        t.input_ids = [s1.id]
        t.output_ids = [s2.id]
        #print(f'{s1.details=} hash={sha256(packify.pack(s1.details)).digest().hex()}')
        #print(f'{s2.details=} hash={sha256(packify.pack(s2.details)).digest().hex()}')
        assert t.validate()

    def test_std_series_covenant_compiles_without_error(self):
        s = models.Txn.std_series_covenant()
        assert type(s) is Script

    def test_stamp_series_with_mint_lock_and_std_series_covenant_e2e(self):
        c1 = models.Coin.mine(ANYONE_CAN_SPEND_LOCK)
        c1.save()

        series_details = {
            'm': {'name': '$HIT Coin (test)'},
            'L': SINGLE_SIG_LOCK.bytes,
            '$': models.Txn.std_series_covenant().bytes,
        }
        second_series_details = {
            'm': {'name': 'fAuxUSD (test)'},
            'L': SINGLE_SIG_LOCK.bytes,
            '$': models.Txn.std_series_covenant().bytes,
        }

        s1 = models.Coin.stamp(
            ANYONE_CAN_SPEND_LOCK, c1.amount - 1000, 1000, series_details
        )
        s1.save()

        # stamping of new series from unstamped coin should work
        t1 = models.Txn({'input_ids': c1.id, 'output_ids': s1.id})
        assert not t1.validate()
        t1.witness = {
            c1.id_bytes: b'',
            s1.id_bytes: make_single_sig_witness(SKEY, t1.runtime_cache(s1)).bytes,
        }
        assert t1.validate(), 'stamping of new series from unstamped coin should work'

        # creating new stamp n-units during transaction should fail
        s2 = models.Coin.stamp(
            ANYONE_CAN_SPEND_LOCK, s1.amount - 1200, 9999, series_details
        )
        s2.save()
        t2 = models.Txn({'input_ids': s1.id, 'output_ids': s2.id})
        t2.witness = {
            s1.id_bytes: b'',
        }
        assert not t2.validate(), 'creating new stamp n-units during txn should fail'

        # mixing stamps of different series in a transaction should fail
        sX = models.Coin.stamp(
            ANYONE_CAN_SPEND_LOCK, s1.amount - 1530, 420, second_series_details
        )
        sX.save()
        tX = models.Txn({'input_ids': s1.id + ',' + sX.id, 'output_ids': s2.id})
        assert tX.minimum_fee(tX) + sX.amount < s1.amount, \
            'test fails to reflect correct fee calculation'
        assert not tX.validate(), 'mixing stamps with different msh should not validate'

        # simple transfer should work
        s2 = models.Coin.stamp(
            ANYONE_CAN_SPEND_LOCK, s1.amount - 1100, 1000, series_details
        )
        # NB: fee was 1023 when this test was written
        s2.save()
        t2 = models.Txn({'input_ids': s1.id, 'output_ids': s2.id})
        t2.witness = {
            s1.id_bytes: b'',
        }
        while t2.minimum_fee(t2) + s2.amount > s1.amount:
            print('Warning: fee estimation changed; recalculating s2.amount')
            s2.delete()
            # fail-safe in case fee calculation changes so the test doesn't fail
            s2.amount = s1.amount - t2.minimum_fee(t2) - 100
            s2.save()
            t2.output_ids = [s2.id]
        assert t2.validate(), 'simple transfer w/ proper fee burn should work'


if __name__ == '__main__':
    unittest.main()


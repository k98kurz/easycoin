from context import models
from dataclasses import dataclass, field
from genericpath import isfile
from hashlib import sha256
from sqlite3 import OperationalError
from tapehash import calculate_difficulty, tapehash3
from tapescript import Script
import os
import sqloquent
import unittest



DB_FILEPATH = 'tests/test.db'
MIGRATIONS_PATH = 'tests/migrations'
ANYONE_CAN_SPEND_LOCK = Script.from_src('true')


def make_hashlock(preimage: bytes):
    return Script.from_src(
        f'sha256 push x{sha256(preimage).digest().hex()} equal'
    )


class UTXOSet:
    def add(self, coin_id: bytes|str):
        coin_id = coin_id.hex() if type(coin_id) is bytes else coin_id
        models.Output.insert({'id': coin_id})

    def remove(self, coin_id: bytes|str):
        coin_id = coin_id.hex() if type(coin_id) is bytes else coin_id
        models.Input.insert({'id': coin_id})
        models.Output.query({'id': coin_id}).delete()

    def exists(self, coin_id: bytes|str) -> bool:
        coin_id = coin_id.hex() if type(coin_id) is bytes else coin_id
        return models.Output.query({'id': coin_id}).count() == 1

    def has_been_removed(self, coin_id: bytes|str) -> bool:
        coin_id = coin_id.hex() if type(coin_id) is bytes else coin_id
        return models.Input.query({'id': coin_id}).count() == 1


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
        t.witness = {"some sha256 coin id": ANYONE_CAN_SPEND_LOCK.bytes}
        assert type(t.data['witness']) is bytes

    def test_witness_raises_TypeError_for_invalid_data(self):
        t = models.Txn()
        with self.assertRaises(TypeError):
            t.witness = "Not a dict"
        with self.assertRaises(TypeError):
            t.witness = {
                b'not str': ANYONE_CAN_SPEND_LOCK.bytes,
            }
        with self.assertRaises(TypeError):
            t.witness = {
                "some sha256 coin id": "Not bytes",
            }

    def test_minimum_fee_returns_int_that_scales_with_witness_size(self):
        t = models.Txn({'output_ids': '', 'input_ids': ''})
        mf1 = models.Txn.minimum_fee(t)
        assert type(mf1) is int and mf1 > 0

        t.witness = {
            "input1 id": ANYONE_CAN_SPEND_LOCK.bytes,
        }
        mf2 = models.Txn.minimum_fee(t)
        assert mf2 > mf1

        t.witness = {
            "input1 id": ANYONE_CAN_SPEND_LOCK.bytes,
            "input2 id": ANYONE_CAN_SPEND_LOCK.bytes,
        }
        mf3 = models.Txn.minimum_fee(t)
        assert mf3 > mf2

    def test_minimum_fee_returns_int_that_does_not_scale_with_input_count(self):
        t = models.Txn({'output_ids': '', 'input_ids': ''})
        mf1 = models.Txn.minimum_fee(t)
        assert type(mf1) is int and mf1 > 0

        t.input_ids = '123'
        mf2 = models.Txn.minimum_fee(t)
        assert mf2 == mf1

        t.input_ids = '123,321'
        mf3 = models.Txn.minimum_fee(t)
        assert mf3 == mf2

    def test_minimum_fee_returns_int_that_scales_with_output_count(self):
        t = models.Txn({'output_ids': '', 'input_ids': ''})
        mf1 = models.Txn.minimum_fee(t)
        assert type(mf1) is int and mf1 > 0

        t.output_ids = '123,321'
        mf2 = models.Txn.minimum_fee(t)
        assert mf2 > mf1

        t.output_ids = '123,321,456'
        mf3 = models.Txn.minimum_fee(t)
        assert mf3 > mf2

    def test_minimum_fee_returns_int_that_scales_with_output_len(self):
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 999)
        c.save()
        t = models.Txn({'output_ids': c.id, 'input_ids': ''})
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
        assert not t.validate(UTXOSet())

    def test_validate_accepts_mint_txn_that_meets_difficulty_threshold(self):
        c = models.Coin.mine(ANYONE_CAN_SPEND_LOCK)
        c.save()
        t = models.Txn({'output_ids': c.id, 'input_ids':''})
        #print(f'2 {c.mint_value()=}, {c.amount=}')
        assert t.validate(UTXOSet())


if __name__ == '__main__':
    unittest.main()


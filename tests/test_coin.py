from context import models
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


class TestCoin(unittest.TestCase):
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

    def test_lock_property_serializes_properly(self):
        c = models.Coin()
        c.lock = Script.from_src('true')
        assert type(c.lock) is bytes
        assert c.lock == Script.from_src('true').bytes
        assert type(c.data['lock']) is bytes

    def test_lock_property_raises_TypeError_for_bad_input(self):
        c = models.Coin()
        with self.assertRaises(TypeError):
            c.lock = "not a script"

    def test_details_property_serializes_properly(self):
        c = models.Coin()
        c.details = {
            'id': sha256(b'test').digest()
        }
        assert type(c.details) is dict
        assert type(c.data['details']) is bytes

    def test_details_property_raises_TypeError_for_bad_inputs(self):
        c = models.Coin()
        with self.assertRaises(TypeError):
            c.details = "Not a dict"

    def test_create_result_id_depends_on_arguments(self):
        c1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 9999)
        c2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1111)
        c2.timestamp = c1.timestamp
        c3 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 9999, b'some network')
        c3.timestamp = c1.timestamp
        assert c1.id_bytes != c2.id_bytes
        assert c1.id_bytes != c3.id_bytes
        assert c2.id_bytes != c3.id_bytes

    def test_create_result_serializes_and_deserializes_correctly(self):
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 9999)
        assert isinstance(c, models.Coin)
        packed = c.pack()
        unpacked = models.Coin.unpack(packed)
        for k,v in c.data.items():
            assert k in unpacked.data
            assert unpacked.data[k] == v

    def test_mine_result_passes_difficulty_threshold(self):
        threshold = 128 + 10
        c = models.Coin.mine(ANYONE_CAN_SPEND_LOCK)
        assert calculate_difficulty(tapehash3(bytes.fromhex(c.generate_id(c.data)))) >= threshold
        assert c.mint_value() >= c.amount

    def test_stamp_method_returns_coin(self):
        c = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 999, "test")
        assert isinstance(c, models.Coin)
        assert 'id' in c.details
        assert type(c.details['id']) is bytes
        assert 'n' in c.details
        assert c.details['n'] == "test"


if __name__ == '__main__':
    unittest.main()


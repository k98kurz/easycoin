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

    def test_details_property_raises_ValueError_for_details_over_max_size(self):
        c = models.Coin()
        with self.assertRaises(ValueError):
            c.details = {'1': '0' * 10240}

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

    def test_mine_with_low_amount_raises_ValueError(self):
        with self.assertRaises(ValueError):
            models.Coin.mine(ANYONE_CAN_SPEND_LOCK, 1)

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

    def test_dsh_property_derives_consistent_hash(self):
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 999, "test")
        dsh1 = c.dsh
        assert c.dsh == dsh1, 'should not change between derivations'
        s1 = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 999, "test")
        s2 = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 888, "stet")
        s3 = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 777, "with details", {
            'd': {'t': 'txt', 'd': 'some test text'}
        })
        s4 = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 333, "with same details", {
            'd': {'t': 'txt', 'd': 'some test text'}
        })
        assert s1.dsh == c.dsh
        assert s1.dsh == s2.dsh
        assert s3.dsh != s1.dsh
        assert s3.dsh == s4.dsh


if __name__ == '__main__':
    unittest.main()


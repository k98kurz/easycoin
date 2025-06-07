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


class TestChunksAndSnapshots(unittest.TestCase):
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

    def test_Chunk_from_leaves(self):
        ...

    def test_Chunk_relations_e2e(self):
        ...

    def test_Snapshot_without_chunks(self):
        ...

    def test_Snapshot_with_chunks(self):
        ...

    def test_Snapshot_relations_e2e(self):
        ...


if __name__ == '__main__':
    unittest.main()


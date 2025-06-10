from context import models
from genericpath import isfile
from hashlib import sha256
from nacl.signing import SigningKey
from sqlite3 import OperationalError
from tapehash import calculate_difficulty, tapehash3
from tapescript import Script, make_single_sig_lock, make_single_sig_witness
import os
import sqloquent
import unittest


DB_FILEPATH = 'tests/test.db'
MIGRATIONS_PATH = 'tests/migrations'
ANYONE_CAN_SPEND_LOCK = Script.from_src('true')
SKEY = os.urandom(32)
SINGLE_SIG_LOCK = make_single_sig_lock(SigningKey(SKEY).verify_key)


class TestChunksAndSnapshots(unittest.TestCase):
    trustnet: models.TrustNet

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
        self.trustnet = models.TrustNet({
            'name': 'Unit Test Suite', 'lock': SINGLE_SIG_LOCK.bytes,
        })
        self.trustnet.features = 65535
        self.trustnet.save()
        self.net_state = os.urandom(32)
        c = models.Coin.create(
            ANYONE_CAN_SPEND_LOCK, 1000000, self.trustnet.id_bytes,
            self.net_state
        ).save()
        self.osize = len(models.Output.from_coin(c).pack_compact())
        c.delete()
        super().setUp()

    def test_Chunk_create_e2e(self):
        leaves = lambda l, s: [
            (i%256).to_bytes(1, 'big') * s
            for i in range(l)
        ]
        # happy path
        chunk = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OUTPUTS, leaves(12, self.osize)
        )
        chunk.save()
        # too many leaves
        with self.assertRaises(ValueError) as e:
            models.Chunk.create(
                self.trustnet.id, 0, models.ChunkKind.OUTPUTS,
                leaves(1025, 1)
            )
        assert 'leaves' in str(e.exception)
        # too large overall
        with self.assertRaises(ValueError) as e:
            models.Chunk.create(
                self.trustnet.id, 0, models.ChunkKind.OUTPUTS,
                leaves(1024, 61)
            )
        assert 'size' in str(e.exception)

    def test_Snapshot_without_chunks(self):
        snapshot = models.Snapshot.create(self.trustnet.id, params=b'test')
        state = snapshot.calculate_state()
        assert type(state) is bytes, \
            f'state should be bytes, not {type(state)}'
        assert snapshot.calculate_state() == state, \
            'state calculation should be deterministic'
        cache = snapshot.runtime_cache()
        assert type(cache) is dict
        snapshot.witness = b''
        snapshot.save()
        assert snapshot.calculate_state() == state, \
            'state calculation should not depend upon witness or record id'
        assert not snapshot.validate(), \
            'invalid witness should not validate'
        snapshot.witness = make_single_sig_witness(SKEY, cache).bytes
        snapshot.save()
        snapshot.trustnet().reload()
        assert snapshot.calculate_state() == state, \
            'state calculation should not depend upon witness or record id'
        assert snapshot.validate(), snapshot.validate(debug='Snapshot_without_chunks')

    def test_Snapshot_with_chunks(self):
        leaves = lambda l, s: [
            (i%256).to_bytes(1, 'big') * s
            for i in range(l)
        ]
        chunk = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OUTPUTS, leaves(12, self.osize)
        )
        chunk.save()
        snapshot = models.Snapshot.create(self.trustnet.id, chunks = [chunk.id])
        state = snapshot.calculate_state()
        assert type(state) is bytes, \
            f'state should be bytes, not {type(state)}'
        assert snapshot.calculate_state() == state, \
            'state calculation should be deterministic'
        cache = snapshot.runtime_cache()
        assert type(cache) is dict
        snapshot.witness = b''
        snapshot.save()
        assert snapshot.calculate_state() == state, \
            'state calculation should not depend upon witness or record id'
        assert not snapshot.validate(), \
            'invalid witness should not validate'
        snapshot.witness = make_single_sig_witness(SKEY, cache).bytes
        snapshot.save()
        snapshot.trustnet().reload()
        assert snapshot.calculate_state() == state, \
            'state calculation should not depend upon witness or record id'
        assert snapshot.validate(), snapshot.validate(debug='Snapshot_without_chunks')

    def test_Chunk_and_Snapshot_relations_e2e(self):
        leaves = lambda l, s: [
            (i%256).to_bytes(1, 'big') * s
            for i in range(l)
        ]
        chunk0 = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OUTPUTS, leaves(12, self.osize)
        )
        chunk0.save()
        assert chunk0.trustnet.id == self.trustnet.id

        chunk1 = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OUTPUTS, leaves(12, self.osize),
            [chunk0.id]
        )
        chunk1.save()
        assert chunk1.parents
        assert len(chunk1.parents) == 1
        assert chunk1.parents[0].id == chunk0.id

        snapshot = models.Snapshot.create(self.trustnet.id, chunks = [chunk1.id])
        snapshot.witness = make_single_sig_witness(SKEY, snapshot.runtime_cache()).bytes
        snapshot.save()
        assert snapshot.trustnet.id == self.trustnet.id
        assert len(snapshot.chunks) == 1
        assert chunk1 in snapshot.chunks
        assert snapshot in chunk1.snapshots


if __name__ == '__main__':
    unittest.main()


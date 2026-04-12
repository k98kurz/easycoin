from context import models
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


class TestTrustNetsChunksAndSnapshots(unittest.TestCase):
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

    def test_TrustNet_serialization(self):
        packed = self.trustnet.pack()
        assert type(packed) is bytes
        unpacked = models.TrustNet.unpack(packed)
        assert type(unpacked) is models.TrustNet
        assert unpacked.id == self.trustnet.id

    def test_TrustNetFeatures_e2e(self):
        trustnet1 = models.TrustNet({
            'name': 'Test', 'lock': ANYONE_CAN_SPEND_LOCK.bytes,
        }).save()
        assert trustnet1.features == set()
        assert len(trustnet1.params.keys()) == 0
        trustnet2 = models.TrustNet({
            'name': 'Test', 'lock': ANYONE_CAN_SPEND_LOCK.bytes,
        })
        assert len(trustnet2.params.keys()) == 0
        trustnet2.features = {
            models.TrustNetFeature.SNAPSHOT_OUTPUTS,
            models.TrustNetFeature.LOCK_SNAPSHOT,
            models.TrustNetFeature.LOCK_MEMBERS,
        }
        assert len(trustnet2.params.keys()) == 1
        trustnet2.save()
        assert 'features' in trustnet2.params
        assert trustnet1.id != trustnet2.id

    def test_Chunk_empty_packify_properties_do_not_error(self):
        chunk = models.Chunk()
        chunk.data['leaves'] = None
        assert len(chunk.leaves) == 0

    def test_Chunk_create_e2e(self):
        leaves = lambda l, s: [
            (i%256).to_bytes(1, 'big') * s
            for i in range(l)
        ]
        # happy path
        chunk = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OTHER, leaves(12, self.osize)
        )
        chunk.save()
        # too many leaves
        with self.assertRaises(ValueError) as e:
            models.Chunk.create(
                self.trustnet.id, 0, models.ChunkKind.OTHER,
                leaves(1025, 1)
            )
        assert 'leaves' in str(e.exception)
        # too large overall
        with self.assertRaises(ValueError) as e:
            models.Chunk.create(
                self.trustnet.id, 0, models.ChunkKind.OTHER,
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
            self.trustnet.id, 0, models.ChunkKind.OTHER, leaves(12, self.osize)
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
        # NB: ChunkKind.OTHER with non-None net_id is only okay in test context
        chunk0 = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OTHER, leaves(12, self.osize)
        )
        chunk0.save()
        assert chunk0.trustnet.id == self.trustnet.id

        chunk1 = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OTHER, leaves(12, self.osize),
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

    def test_Chunk_validate_e2e(self):
        leaves = lambda l, s: [
            (i%256).to_bytes(1, 'big') * s
            for i in range(l)
        ]
        chunk = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OUTPUTS, leaves(12, self.osize)
        )
        chunk.save()
        assert chunk.validate(), 'valid chunk should pass validation'

    def test_Chunk_validate_OTHER_kind_e2e(self):
        leaves = [b'\x00', b'\x01']
        chunk = models.Chunk.create(
            None, 0, models.ChunkKind.OTHER, leaves
        )
        assert chunk.validate(debug='OTHER_kind'), \
            'OTHER kind should pass validation without TrustNet'

    def test_Chunk_validate_invalid_merkle_root_e2e(self):
        leaves = lambda l, s: [
            (i%256).to_bytes(1, 'big') * s
            for i in range(l)
        ]
        chunk = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OUTPUTS, leaves(12, self.osize)
        )
        chunk.data['root'] = b'\xff' * 32
        assert not chunk.validate(), (
            'chunk with corrupted Merkle root should fail validation: '
            f"{chunk.validate(debug='corrupted_merkle')}"
        )

    def test_Chunk_validate_disallowed_kind_e2e(self):
        trustnet = models.TrustNet({
            'name': 'Test', 'lock': ANYONE_CAN_SPEND_LOCK.bytes,
        })
        trustnet.features = {models.TrustNetFeature.SNAPSHOT_OUTPUTS}
        trustnet.save()

        leaves = [b'0', b'1']
        chunk = models.Chunk.create(
            trustnet.id, 0, models.ChunkKind.INPUTS, leaves
        )
        assert not chunk.validate(), (
            'chunk with disallowed kind should fail validation: '
            f"{chunk.validate(debug='disallowed_kind')}"
        )

    def test_Chunk_apply_OUTPUTS_e2e(self):
        outputs = []
        for i in range(5):
            c = models.Coin.create(
                ANYONE_CAN_SPEND_LOCK, 1000000 + i, self.trustnet.id_bytes,
                self.net_state
            ).save()
            o = models.Output.from_coin(c)
            outputs.append(o)
        chunk = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.OUTPUTS,
            [o.pack_compact() for o in outputs]
        )
        chunk.save()

        count, errors = chunk.apply()
        assert count == 5, f'expected 5 processed records, got {count}'
        assert len(errors) == 0, f'expected no errors, got {errors}'
        for o in outputs:
            found = models.Output.query({'id': o.id}).first()
            assert found is not None, f'Output {o.id} not found in database'
            assert found.id == o.id, 'Output ID mismatch'

        # idempotency check
        count, errors = chunk.apply()
        assert count == 5, f'expected 5 processed records, got {count}'
        assert len(errors) == 0, f'expected no errors, got {errors}'
        total_outputs = len(models.Output.query().get())
        assert total_outputs == 5, f'expected 5 unique outputs, got {total_outputs}'

    def test_Chunk_apply_INPUTS_e2e(self):
        coins = []
        inputs = []
        for i in range(3):
            c = models.Coin.create(
                ANYONE_CAN_SPEND_LOCK, 1000000 + i, self.trustnet.id_bytes,
                self.net_state
            ).save()
            coins.append(c)
            i_input = models.Input({'id': c.id})
            inputs.append(i_input)
        for c in coins:
            o = models.Output.from_coin(c)
            o.save()
        chunk = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.INPUTS,
            [i.pack_compact() for i in inputs]
        )
        chunk.save()
        count, errors = chunk.apply()
        assert count == 9, f'expected 9 processed records, got {count}'
        assert len(errors) == 0, f'expected no errors, got {errors}'
        for c in coins:
            found = models.Input.query({'id': c.id}).first()
            assert found is not None, f'Input for {c.id} not found'
            assert not models.Output.query({'id': c.id}).first(), \
                f'Output for {c.id} should be deleted'
            found_coin = models.Coin.find(c.id)
            assert found_coin is not None, f'Coin {c.id} not found'
            assert found_coin.spent, f'Coin {c.id} should be marked as spent'

    def test_Chunk_apply_TXNS_e2e(self):
        input_coins = []
        output_coins = []
        for i in range(2):
            c = models.Coin.create(
                ANYONE_CAN_SPEND_LOCK, 1000000 + i, self.trustnet.id_bytes,
                self.net_state
            ).save()
            input_coins.append(c)
        for i in range(3):
            c = models.Coin.create(
                ANYONE_CAN_SPEND_LOCK, 1000010 + i, self.trustnet.id_bytes,
                self.net_state
            ).save()
            output_coins.append(c)
        t = models.Txn()
        t.input_ids = [c.id for c in input_coins]
        t.output_ids = [c.id for c in output_coins]
        t.witness = {input_coins[0].id_bytes: ANYONE_CAN_SPEND_LOCK.bytes}
        txn_packed = t.pack()
        for c in input_coins:
            c.delete()
        for c in output_coins:
            c.delete()
        chunk = models.Chunk.create(
            self.trustnet.id, 0, models.ChunkKind.TXNS, [txn_packed, b'\x00' * 100]
        )
        chunk.save()
        count, errors = chunk.apply()
        assert count == 6, f'expected 6 processed records, got {count}'
        assert len(errors) == 1, (
            f'expected 1 error for invalid second leaf, got {len(errors)}'
        )
        for c in input_coins:
            found_coin = models.Coin.find(c.id)
            assert found_coin is not None, f'Input coin {c.id} not found'
            assert found_coin.spent, f'Input coin {c.id} should be marked as spent'
        for c in output_coins:
            found_coin = models.Coin.find(c.id)
            assert found_coin is not None, f'Output coin {c.id} not found'
            assert not found_coin.spent, (
                f'Output coin {c.id} should not be marked as spent'
            )
        found_txn = models.Txn.query().first()
        assert found_txn is not None, 'Transaction not found in database'

    def test_Chunk_apply_invalid_chunk_e2e(self):
        leaves = [b'\x00', b'\x01']
        chunk = models.Chunk({
            'net_id': self.trustnet.id, 'idx': 0,
            'kind': models.ChunkKind.OUTPUTS.value, 'root': b'\xff' * 32,
            'leaves': packify.pack(tuple(leaves))
        })
        count, errors = chunk.apply()
        assert count == 0, f'expected 0 processed records, got {count}'
        assert len(errors) == 1, f'expected 1 error, got {len(errors)}'
        assert isinstance(errors[0], ValueError), 'expected ValueError'
        assert 'cannot apply an invalid Chunk' in str(errors[0]), (
            f'expected specific error message, got {errors[0]}'
        )


if __name__ == '__main__':
    unittest.main()


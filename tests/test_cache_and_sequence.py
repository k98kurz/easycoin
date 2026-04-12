from context import constants, models, cache, sequence
from genericpath import isfile
from merkleasy import Tree
from os import remove
from tapescript import Script
import os
import unittest


DB_FILEPATH = 'tests/test.db'
MIGRATIONS_PATH = 'tests/migrations'
ANYONE_CAN_SPEND_LOCK = Script.from_src('true')


class TestCacheAndSequence(unittest.TestCase):
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
                remove(f'{MIGRATIONS_PATH}/{file}')
        if isfile(DB_FILEPATH):
            remove(DB_FILEPATH)
        super().tearDownClass()

    def setUp(self):
        cache._caches.clear()
        for m in [
                models.Coin, models.Txn, models.Wallet,
                models.Input, models.Output
            ]:
            m.query().delete()
        super().setUp()

    def test_LRUCache_get_instance_singleton(self):
        c1 = cache.LRUCache.get_instance('test', cache.CacheKind.RECEIVE, 10)
        c2 = cache.LRUCache.get_instance('test', cache.CacheKind.RECEIVE, 10)
        assert c1 is c2, 'should return same instance'

    def test_LRUCache_duplicate_instantiation_raises_ValueError(self):
        cache.LRUCache('test', cache.CacheKind.RECEIVE, 10)
        with self.assertRaises(ValueError) as e:
            cache.LRUCache('test', cache.CacheKind.RECEIVE, 10)
        assert 'cannot instantiate the same LRUCache twice' in str(e.exception)

    def test_LRUCache_get_updates_LRU_order(self):
        c = cache.LRUCache('test', cache.CacheKind.RECEIVE, 3)
        c.put('key1', 'value1')
        c.put('key2', 'value2')
        c.put('key3', 'value3')
        c.get('key1')
        c.put('key4', 'value4')
        assert c.get('key1') == 'value1', 'key1 should still exist'
        assert c.get('key2') is None, 'key2 should be evicted'
        assert c.get('key3') == 'value3', 'key3 should still exist'
        assert c.get('key4') == 'value4', 'key4 should exist'

    def test_LRUCache_peak_does_not_update_LRU_order(self):
        c = cache.LRUCache('test', cache.CacheKind.RECEIVE, 3)
        c.put('key1', 'value1')
        c.put('key2', 'value2')
        c.put('key3', 'value3')
        c.peak('key1')
        c.put('key4', 'value4')
        assert c.get('key1') is None, 'key1 should be evicted'
        assert c.get('key2') == 'value2', 'key2 should still exist'
        assert c.get('key3') == 'value3', 'key3 should still exist'
        assert c.get('key4') == 'value4', 'key4 should exist'

    def test_LRUCache_put_enforces_limit_and_evicts_LRU(self):
        c = cache.LRUCache('test', cache.CacheKind.RECEIVE, 3)
        c.put('key1', 'value1')
        c.put('key2', 'value2')
        c.put('key3', 'value3')
        assert len(c.od) == 3
        c.put('key4', 'value4')
        assert len(c.od) == 3
        assert c.get('key1') is None, 'key1 should be evicted'
        assert c.get('key4') == 'value4', 'key4 should exist'

    def test_LRUCache_pop_removes_item(self):
        c = cache.LRUCache('test', cache.CacheKind.RECEIVE, 10)
        c.put('key1', 'value1')
        result = c.pop('key1')
        assert result == 'value1'
        assert c.get('key1') is None
        assert c.pop('nonexistent') is None

    def test_Part_validate_checks_constraints(self):
        tree = Tree.from_leaves([b'test_data', b''])
        proof = tree.prove(b'test_data')
        part = sequence.Part(
            'Coin', 'test_id', 0, tree.root, proof, b'test_data'
        )
        assert part.validate()
        assert part.idx >= 0
        assert part.idx <= constants.MAX_SEQUENCE_SIZE
        assert len(part.blob) <= constants.MAX_PART_SIZE

    def test_Part_validate_rejects_invalid_idx(self):
        tree = Tree.from_leaves([b'test_data', b''])
        proof = tree.prove(b'test_data')
        part = sequence.Part(
            'Coin', 'test_id', -1, tree.root, proof, b'test_data'
        )
        assert not part.validate()
        part.idx = constants.MAX_SEQUENCE_SIZE + 1
        assert not part.validate()

    def test_Part_validate_rejects_oversized_blob(self):
        blob = b'x' * (constants.MAX_PART_SIZE + 1)
        tree = Tree.from_leaves([blob, b''])
        proof = tree.prove(blob)
        part = sequence.Part(
            'Coin', 'test_id', 0, tree.root, proof, blob
        )
        assert not part.validate()

    def test_Part_pack_unpack_roundtrip(self):
        tree = Tree.from_leaves([b'test_data', b''])
        proof = tree.prove(b'test_data')
        part = sequence.Part(
            'Coin', 'test_id', 0, tree.root, proof, b'test_data'
        )
        packed = part.pack()
        unpacked = sequence.Part.unpack(packed)
        assert unpacked.record_type == part.record_type
        assert unpacked.record_id == part.record_id
        assert unpacked.idx == part.idx
        assert unpacked.root == part.root
        assert unpacked.proof == part.proof
        assert unpacked.blob == part.blob

    def test_Part_hash_is_unique(self):
        tree = Tree.from_leaves([b'test_data', b''])
        proof = tree.prove(b'test_data')
        part1 = sequence.Part(
            'Coin', 'test_id', 0, tree.root, proof, b'test_data'
        )
        part2 = sequence.Part(
            'Coin', 'test_id', 0, tree.root, proof, b'test_data'
        )
        part3 = sequence.Part(
            'Coin', 'other_id', 0, tree.root, proof, b'test_data'
        )
        assert hash(part1) == hash(part2)
        assert hash(part1) != hash(part3)

    def test_Sequence_validate_returns_True_for_valid_Sequence(self):
        seq = sequence.Sequence('Coin', 'test_id', b'0' * 32, 1)
        assert seq.validate()
        assert type(seq.record_type) is str
        assert len(seq.record_type)
        assert type(seq.record_id) is str
        assert len(seq.record_id)
        assert type(seq.root) is bytes
        assert len(seq.root) == 32
        assert type(seq.count) is int
        assert seq.count > 0
        assert seq.count <= constants.MAX_SEQUENCE_SIZE

    def test_Sequence_validate_rejects_invalid_data(self):
        seq = sequence.Sequence('', 'test_id', b'0' * 32, 1)
        assert not seq.validate()
        seq.record_type = 'Coin'
        assert seq.validate()
        seq.record_id = ''
        assert not seq.validate()
        seq.record_id = 'test_id'
        assert seq.validate()
        seq.root = b'short'
        assert not seq.validate()
        seq.root = b'0' * 32
        assert seq.validate()
        seq.count = 0
        assert not seq.validate()
        seq.count = constants.MAX_SEQUENCE_SIZE + 1
        assert not seq.validate()

    def test_Sequence_has_part_and_get_part(self):
        tree = Tree.from_leaves([b'test_data', b''])
        proof = tree.prove(b'test_data')
        part = sequence.Part(
            'Coin', 'test_id', 0, tree.root, proof, b'test_data'
        )
        seq = sequence.Sequence('Coin', 'test_id', tree.root, 1, {0: part})
        assert seq.has_part(0)
        assert not seq.has_part(1)
        assert seq.get_part(0) == part
        assert seq.get_part(1) is None

    def test_Sequence_add_part_rejects_invalid_parts(self):
        tree = Tree.from_leaves([b'test_data', b''])
        proof = tree.prove(b'test_data')
        part = sequence.Part(
            'Coin', 'test_id', 0, tree.root, proof, b'test_data'
        )
        seq = sequence.Sequence('Coin', 'test_id', tree.root, 1)
        seq.add_part(part)
        assert 0 in seq.parts

        wrong_root = sequence.Part(
            'Coin', 'test_id', 0, b'1' * 32, proof, b'test_data'
        )
        with self.assertRaises(ValueError) as e:
            seq.add_part(wrong_root)
        assert 'cannot add Part that is not from this Sequence' in str(e.exception)

        invalid_idx = sequence.Part(
            'Coin', 'test_id', 5, tree.root, proof, b'test_data'
        )
        with self.assertRaises(ValueError) as e:
            seq.add_part(invalid_idx)
        assert 'cannot add Part that is not from this Sequence' in str(e.exception)

    def test_Sequence_can_reconstruct(self):
        tree = Tree.from_leaves([b'data1', b'data2'])
        proof1 = tree.prove(b'data1')
        proof2 = tree.prove(b'data2')
        part1 = sequence.Part('Coin', 'test_id', 0, tree.root, proof1, b'data1')
        part2 = sequence.Part('Coin', 'test_id', 1, tree.root, proof2, b'data2')
        seq = sequence.Sequence('Coin', 'test_id', tree.root, 2)
        assert not seq.can_reconstruct()
        seq.add_part(part1)
        assert not seq.can_reconstruct()
        seq.add_part(part2)
        assert seq.can_reconstruct()

    def test_Sequence_reconstruct_raises_ValueError_when_incomplete(self):
        tree = Tree.from_leaves([b'data1', b'data2'])
        proof1 = tree.prove(b'data1')
        part1 = sequence.Part('Coin', 'test_id', 0, tree.root, proof1, b'data1')
        seq = sequence.Sequence('Coin', 'test_id', tree.root, 2, {0: part1})
        with self.assertRaises(ValueError) as e:
            seq.reconstruct()
        assert 'cannot reconstruct when missing parts' in str(e.exception)

    def test_Sequence_reconstruct_assembles_parts_in_order(self):
        tree = Tree.from_leaves([b'data1', b'data2', b'data3'])
        proofs = [tree.prove(b'data1'), tree.prove(b'data2'), tree.prove(b'data3')]
        parts = {
            2: sequence.Part('Coin', 'test_id', 2, tree.root, proofs[2], b'data3'),
            0: sequence.Part('Coin', 'test_id', 0, tree.root, proofs[0], b'data1'),
            1: sequence.Part('Coin', 'test_id', 1, tree.root, proofs[1], b'data2'),
        }
        seq = sequence.Sequence('Coin', 'test_id', tree.root, 3, parts)
        reconstructed = seq.reconstruct()
        assert reconstructed == b'data1data2data3'

    def test_Sequence_pack_unpack_roundtrip(self):
        tree = Tree.from_leaves([b'data1', b'data2'])
        proofs = [tree.prove(b'data1'), tree.prove(b'data2')]
        parts = {
            0: sequence.Part('Coin', 'test_id', 0, tree.root, proofs[0], b'data1'),
            1: sequence.Part('Coin', 'test_id', 1, tree.root, proofs[1], b'data2'),
        }
        seq = sequence.Sequence('Coin', 'test_id', tree.root, 2, parts)
        packed = seq.pack()
        unpacked = sequence.Sequence.unpack(packed)
        assert unpacked.record_type == seq.record_type
        assert unpacked.record_id == seq.record_id
        assert unpacked.root == seq.root
        assert unpacked.count == seq.count

    def test_prepare_sequence_creates_parts_from_record(self):
        coin = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1000)
        coin.id = 'test_coin_id'
        seq = sequence.prepare_sequence(coin)
        assert seq.record_type == 'Coin'
        assert seq.record_id == 'test_coin_id'
        assert len(seq.parts) > 0
        assert seq.count == len(seq.parts)
        for idx, part in seq.parts.items():
            assert part.idx == idx
            assert part.record_type == 'Coin'
            assert part.record_id == 'test_coin_id'
            assert part.root == seq.root

    def test_get_sequence_cache_workflow_e2e(self):
        big_n = b'0' * 400_000
        coin = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 1_000_000, big_n).save()
        coin_id = coin.id

        seq1 = sequence.get_sequence(
            models.Coin, coin_id, cache.CacheKind.RECEIVE
        )
        assert seq1.record_id == coin_id
        assert seq1.can_reconstruct()
        reconstructed1 = seq1.reconstruct()
        assert reconstructed1 == coin.pack()

        seq2 = sequence.get_sequence(
            models.Coin, coin_id, cache.CacheKind.RECEIVE
        )
        assert seq1 is seq2, 'should return cached instance'

        seq3 = sequence.get_sequence(
            models.Coin, coin_id, cache.CacheKind.SEND
        )
        assert seq3 is seq1, 'should return same instance from cross-fill'
        assert seq3.record_id == coin_id

    def test_get_part_cache_workflow_e2e(self):
        big_n = b'0' * 400_000
        coin = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 1_000_000, big_n).save()
        coin_id = coin.id

        primary_cache = cache.LRUCache.get_instance(
            'parts', cache.CacheKind.RECEIVE
        )
        primary_cache.clear()
        assert len(primary_cache.od) == 0

        secondary_cache = cache.LRUCache.get_instance(
            'parts', cache.CacheKind.SEND
        )
        secondary_cache.clear()
        assert len(secondary_cache.od) == 0

        part1 = sequence.get_part(
            models.Coin, coin_id, cache.CacheKind.RECEIVE, 0
        )
        assert part1.idx == 0
        assert len(primary_cache.od) > 0
        assert len(secondary_cache.od) == 0

        part2 = sequence.get_part(
            models.Coin, coin_id, cache.CacheKind.RECEIVE, 0
        )
        assert part1 is part2, 'should return cached part'
        assert len(secondary_cache.od) == 0

        part3 = sequence.get_part(
            models.Coin, coin_id, cache.CacheKind.SEND, 0
        )
        assert part3 is part1, 'should return same instance from cross-fill'
        assert part3.idx == 0
        assert len(secondary_cache.od) > 0

    def test_get_sequence_secondary_cache_populates_primary(self):
        big_n = b'0' * 400_000
        coin = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 1_000_000, big_n).save()
        coin_id = coin.id

        primary_cache = cache.LRUCache.get_instance(
            'sequences', cache.CacheKind.RECEIVE
        )
        primary_cache.clear()
        assert len(primary_cache.od) == 0

        secondary_cache = cache.LRUCache.get_instance(
            'sequences', cache.CacheKind.SEND
        )
        secondary_cache.clear()
        assert len(secondary_cache.od) == 0

        seq1 = sequence.get_sequence(
            models.Coin, coin_id, cache.CacheKind.RECEIVE
        )
        assert seq1.record_id == coin_id
        assert len(primary_cache.od) > 0
        assert len(secondary_cache.od) == 0

        seq2 = sequence.get_sequence(
            models.Coin, coin_id, cache.CacheKind.SEND
        )
        assert seq2 is seq1, 'should get from primary cache after cross-fill'
        assert len(secondary_cache.od) > 0


if __name__ == '__main__':
    unittest.main()

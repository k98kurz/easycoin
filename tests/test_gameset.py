from context import easycoin, gameset, models
from genericpath import exists, isfile
from os import mkdir, rmdir, remove, listdir
from random import randint
from tapescript import Script
import os
import unittest


DB_FILEPATH = 'tests/test.db'
MIGRATIONS_PATH = 'tests/migrations'
ANYONE_CAN_SPEND_LOCK = Script.from_src('true')
NOBODY_CAN_SPEND_LOCK = Script.from_src('false')


class TestGameSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(MIGRATIONS_PATH, exist_ok=True)
        models.set_connection_info(DB_FILEPATH)
        models.publish_migrations(MIGRATIONS_PATH)
        models.automigrate(MIGRATIONS_PATH, DB_FILEPATH)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        for file in listdir(MIGRATIONS_PATH):
            filepath = f'{MIGRATIONS_PATH}/{file}'
            if isfile(filepath):
                remove(filepath)

        backups = [f"tests/{f}" for f in os.listdir('tests/') if f.endswith('.db-backup')]
        for filepath in [DB_FILEPATH, 'tests/test_gameset.zip', *backups]:
            if isfile(filepath):
                remove(filepath)

        super().tearDownClass()

    def setUp(self):
        for m in [
                models.Coin, models.Txn, models.Wallet,
                models.Input, models.Output, models.Address
            ]:
            m.query().delete()

    def test_create_gameset_empty_db_raises_ValueError(self):
        with self.assertRaises(ValueError) as e:
            gameset.create_gameset('tests/test_gameset.zip')
        assert 'all tables are empty' in str(e.exception)

    def test_create_gameset_with_data(self):
        coin1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 10**6).save()
        coin2 = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 10**6, 69420).save()

        txn = models.Txn({})
        txn.input_ids = [coin1.id]
        txn.output_ids = [coin2.id]
        txn.set_timestamp()
        txn.save()

        models.Input.from_coin(coin1).save()
        models.Output.from_coin(coin2).save()

        zip_path = gameset.create_gameset('tests/test_gameset.zip')
        assert isfile(zip_path)

        if isfile(zip_path):
            remove(zip_path)

    def test_create_gameset_invalid_params(self):
        with self.assertRaises(ValueError) as e:
            gameset.create_gameset('')
        assert 'output_filename must not be empty' in str(e.exception)

        with self.assertRaises(TypeError) as e:
            gameset.create_gameset(123)
        assert 'output_filename must be str' in str(e.exception)

    def test_calculate_gameset_hash_and_validate_gameset_hash(self):
        coin1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 10**6).save()

        zip_path = gameset.create_gameset('tests/test_gameset.zip')
        hash1 = gameset.calculate_gameset_hash(zip_path)
        hash2 = gameset.calculate_gameset_hash(zip_path)
        coin2 = models.Coin.stamp(ANYONE_CAN_SPEND_LOCK, 10**6, 69420).save()
        gameset.create_gameset('tests/test_gameset.zip')
        hash3 = gameset.calculate_gameset_hash(zip_path)

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 72
        assert gameset.validate_gameset_hash(hash1)
        assert gameset.validate_gameset_hash(hash3)
        hg = (bytes.fromhex(hash3[:-2])[0] + 1) % 256
        hg = bytes([hg]).hex()
        assert len(hg) == 2, hg
        assert not gameset.validate_gameset_hash(hash3[:70] + hg)
        assert not gameset.validate_gameset_hash(hash3[:64])
        assert isfile(zip_path)

        remove(zip_path)

    def test_create_gameset_apply_gameset_e2e(self):
        assert models.Coin.query().count() == 0, "test precondition failed"
        utxos = easycoin.UTXOSet()
        stamp_details = {
            '_': models.Txn.std_stamp_token_series_prefix().bytes,
            '$': models.Txn.std_stamp_token_series_covenant().bytes
        }
        def create_txns(inputs: int, outputs: int):
            inputs = [
                models.Coin.create(
                    ANYONE_CAN_SPEND_LOCK, randint(10**5, 10**7)
                ).save()
                if i % 2 else
                models.Coin.stamp(
                    NOBODY_CAN_SPEND_LOCK, randint(10**5, 10**7), randint(1, 1000),
                    stamp_details
                ).save()
                for i in range(inputs)
            ]
            outputs = [
                models.Coin.create(
                    ANYONE_CAN_SPEND_LOCK, randint(10**5, 10**7)
                ).save()
                if i % 2 else
                models.Coin.stamp(
                    NOBODY_CAN_SPEND_LOCK, randint(10**5, 10**7), randint(1, 1000),
                    stamp_details
                ).save()
                for i in range(outputs)
            ]
            coins = {
                **{c.id: c for c in inputs},
                **{c.id: c for c in outputs},
            }
            # fund
            txn1 = models.Txn({})
            txn1.output_ids = [c.id for c in inputs]
            txn1.set_timestamp()
            txn1.save()
            utxos.apply(txn1, coins)
            # spend
            txn2 = models.Txn({})
            txn2.input_ids = [c.id for c in inputs]
            txn2.output_ids = [c.id for c in outputs]
            txn2.set_timestamp()
            txn2.save()
            utxos.apply(txn2, coins)
            for i in inputs:
                i.spent = True
                i.save()

        for i in range(6):
            create_txns(randint(1, 10), randint(1,3))

        original_coins = {c.id: c for c in models.Coin.query().get()}
        original_txns = {t.id: t for t in models.Txn.query().get()}
        original_inputs = {i.id: i for i in models.Input.query().get()}
        original_outputs = {o.id: o for o in models.Output.query().get()}

        zip_path = gameset.create_gameset('tests/test_gameset.zip')
        gameset.apply_gameset(zip_path, DB_FILEPATH, MIGRATIONS_PATH)

        backup_files = [f for f in listdir('tests') if f.endswith('.db-backup')]
        assert len(backup_files) > 0

        imported_coins = {c.id: c for c in models.Coin.query().get()}
        imported_txns = {t.id: t for t in models.Txn.query().get()}
        imported_inputs = {i.id: i for i in models.Input.query().get()}
        imported_outputs = {o.id: o for o in models.Output.query().get()}

        assert len(imported_coins) == len(original_coins)
        assert len(imported_txns) == len(original_txns)
        assert len(imported_inputs) == len(original_inputs)
        assert len(imported_outputs) == len(original_outputs)

        for coin_id in original_coins:
            assert coin_id in imported_coins, (coin_id, imported_coins)
            original = original_coins[coin_id]
            imported = imported_coins[coin_id]
            assert original.timestamp == imported.timestamp
            assert original.lock == imported.lock
            assert original.amount == imported.amount
            assert original.spent == imported.spent

        for txn_id in original_txns:
            assert txn_id in imported_txns, (
                txn_id, [
                    v.data
                    for _,v in original_txns.items()
                ], [
                    v.data
                    for _,v in imported_txns.items()
                ]
            )
            original = original_txns[txn_id]
            imported = imported_txns[txn_id]
            assert original.output_ids == imported.output_ids, (original, imported)
            assert original.input_ids == imported.input_ids, (original, imported)
            assert original.timestamp == imported.timestamp, (original, imported)
            assert original.witness == imported.witness, (original, imported)
            assert original.data == imported.data, "Txn data should match exactly"

        for input_id in original_inputs:
            assert input_id in imported_inputs, f"Input ID {input_id} not found"
            original = original_inputs[input_id]
            imported = imported_inputs[input_id]
            assert original.data == imported.data, "Input data should match exactly"

        for output_id in original_outputs:
            assert output_id in imported_outputs, f"Output ID {output_id} not found"
            original = original_outputs[output_id]
            imported = imported_outputs[output_id]
            assert original.data == imported.data, "Output data should match exactly"

        remove(zip_path)
        for f in backup_files:
            remove(f'tests/{f}')

    def test_apply_gameset_with_invalid_params_raises_errors(self):
        coin1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 10**6).save()

        zip_path = gameset.create_gameset('tests/test_gameset.zip')

        with self.assertRaises(ValueError) as e:
            gameset.apply_gameset('', DB_FILEPATH, MIGRATIONS_PATH)
        assert 'gameset_path must not be empty' in str(e.exception)

        with self.assertRaises(TypeError) as e:
            gameset.apply_gameset(123, DB_FILEPATH, MIGRATIONS_PATH)
        assert 'gameset_path must be str' in str(e.exception)

        with self.assertRaises(ValueError) as e:
            gameset.apply_gameset('nonexistent.zip', DB_FILEPATH,
                MIGRATIONS_PATH)
        assert 'must be valid file' in str(e.exception)

        remove(zip_path)

    def test_apply_gameset_with_corrupt_zip_raises_error(self):
        """Test handling of corrupt ZIP file."""
        with open('tests/corrupt.zip', 'wb') as f:
            f.write(b'This is not a valid zip file')

        with self.assertRaises(Exception):
            gameset.apply_gameset(
                'tests/corrupt.zip', DB_FILEPATH, MIGRATIONS_PATH
            )

        if isfile('tests/corrupt.zip'):
            remove('tests/corrupt.zip')


if __name__ == '__main__':
    unittest.main()

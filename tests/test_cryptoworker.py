from context import models, cryptoworker
from asyncio import run, sleep, create_task
from dataclasses import dataclass, field
from genericpath import isfile
from tapescript import Script
import os
import sqloquent
import unittest



DB_FILEPATH = 'tests/test.db'
MIGRATIONS_PATH = 'tests/migrations'
ANYONE_CAN_SPEND_LOCK = Script.from_src('true')


class TestCryptoWorker(unittest.TestCase):
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

    def test_txn_validation_jobs_e2e(self):
        result = run(cryptoworker.work_txn_validation_jobs())
        assert result is None

        c0_1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 99999).save()
        c0_2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 11111).save()
        c1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1111).save()
        c2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 2222).save()
        c3 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 3333).save()
        txn1 = models.Txn({
            'input_ids': c0_1.id,
            'output_ids': ','.join([c1.id, c2.id])
        })
        txn1.id = txn1.generate_id(txn1.data)
        txn2 = models.Txn({
            'input_ids': c0_2.id,
            'output_ids': c3.id
        })
        txn2.id = txn2.generate_id(txn2.data)
        txn3 = models.Txn({
            'input_ids': '',
            'output_ids': ','.join([c1.id, c2.id])
        })
        txn3.id = txn3.generate_id(txn3.data)

        cryptoworker.submit_txn_job(txn1)
        cryptoworker.submit_txn_job(txn2)
        cryptoworker.submit_txn_job(txn3)

        result = run(cryptoworker.work_txn_validation_jobs())
        assert type(result) is list
        assert len(result) == 3
        for jm in result:
            tid = models.Txn.unpack(jm.job_data).id
            if tid == txn1.id:
                assert jm.result is True
            elif tid == txn2.id:
                assert jm.result is True
            elif tid == txn3.id:
                assert jm.result is False

    async def validate_with_task_and_queues(self):
        result = cryptoworker.get_txn_job_result()
        assert result is None
        task = create_task(cryptoworker.work())

        c0_1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 99999).save()
        c0_2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 11111).save()
        c1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1111).save()
        c2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 2222).save()
        c3 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 3333).save()
        txn1 = models.Txn({
            'input_ids': c0_1.id,
            'output_ids': ','.join([c1.id, c2.id])
        })
        txn1.id = txn1.generate_id(txn1.data)
        txn2 = models.Txn({
            'input_ids': c0_2.id,
            'output_ids': c3.id
        })
        txn2.id = txn2.generate_id(txn2.data)
        txn3 = models.Txn({
            'input_ids': '',
            'output_ids': ','.join([c1.id, c2.id])
        })
        txn3.id = txn3.generate_id(txn3.data)

        cryptoworker.submit_txn_job(txn1)
        cryptoworker.submit_txn_job(txn2)
        cryptoworker.submit_txn_job(txn3)

        # wait for worker to finish
        await sleep(0.5)

        result = cryptoworker.get_txn_job_result()
        assert type(result) is cryptoworker.JobMessage
        result = [result]
        job = cryptoworker.get_txn_job_result()
        while job:
            result.append(job)
            job = cryptoworker.get_txn_job_result()
        for jm in result:
            tid = models.Txn.unpack(jm.job_data).id
            if tid == txn1.id:
                assert jm.result is True
            elif tid == txn2.id:
                assert jm.result is True
            elif tid == txn3.id:
                assert jm.result is False

        task.cancel()

    def test_validate_with_task_and_queues(self):
        run(self.validate_with_task_and_queues())

    def test_mine_jobs_e2e(self):
        result = run(cryptoworker.work_mine_job())
        assert result is None

        total_target = 555555
        cryptoworker.submit_mine_job(ANYONE_CAN_SPEND_LOCK.bytes, total_target, 5)
        result = run(cryptoworker.work_mine_job())
        assert type(result) is tuple
        assert len(result) == 2
        assert type(result[0]) is cryptoworker.JobMessage
        assert type(result[1]) is list
        jm, coins = result
        for c in coins:
            assert c.mint_value() >= c.amount
        assert sum([c.amount for c in coins]) >= total_target

    async def mine_with_task_and_queues(self):
        task = create_task(cryptoworker.work())
        result = cryptoworker.get_mined_coins()
        assert result is None

        total_target = 555555
        cryptoworker.submit_mine_job(ANYONE_CAN_SPEND_LOCK.bytes, total_target, 5)

        # wait for the jobs to complete
        await sleep(1)

        coins = cryptoworker.get_mined_coins()
        assert coins is not None

        for c in coins:
            assert c.mint_value() >= c.amount
        assert sum([c.amount for c in coins]) >= total_target

        task.cancel()

    def test_mine_with_task_and_queues(self):
        run(self.mine_with_task_and_queues())


if __name__ == '__main__':
    unittest.main()


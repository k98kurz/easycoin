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

    def test_txn_validation_jobs_e2e(self):
        result = run(cryptoworker.work_txn_validation_jobs())
        assert result is None

        # do not save anything because this must all work with ephemeral data
        c0_1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 99999)
        c0_1.id = c0_1.generate_id(c0_1.data)
        c0_2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 11111)
        c0_2.id = c0_2.generate_id(c0_2.data)
        c1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1111)
        c1.id = c1.generate_id(c1.data)
        c2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 2222)
        c2.id = c2.generate_id(c2.data)
        c3 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 3333)
        c3.id = c3.generate_id(c3.data)
        txn1 = models.Txn({
            'input_ids': c0_1.id,
            'output_ids': ','.join([c1.id, c2.id])
        })
        txn1.id = txn1.generate_id(txn1.data)
        txn1.inputs = [c0_1]
        txn1.outputs = [c1, c2]
        txn2 = models.Txn({
            'input_ids': c0_2.id,
            'output_ids': c3.id
        })
        txn2.id = txn2.generate_id(txn2.data)
        txn2.inputs = [c0_2]
        txn2.outputs = [c3]
        txn3 = models.Txn({
            'input_ids': '',
            'output_ids': ','.join([c1.id, c2.id])
        })
        txn3.id = txn3.generate_id(txn3.data)
        txn3.inputs = []
        txn3.outputs = [c1, c2]

        cryptoworker.submit_txn_job(txn1, debug='txn1 (1)')
        cryptoworker.submit_txn_job(txn2, debug='txn2 (1)')
        cryptoworker.submit_txn_job(txn3, debug='txn3 (1)')

        result = run(cryptoworker.work_txn_validation_jobs())
        assert type(result) is list
        assert len(result) == 3
        for jm in result:
            txn = models.Txn.unpack(jm.job_data)
            if txn.id == txn1.id:
                assert jm.result is True, (txn.inputs, txn.outputs, jm)
            elif txn.id == txn2.id:
                assert jm.result is True, (txn.inputs, txn.outputs, jm)
            elif txn.id == txn3.id:
                assert jm.result is False, (txn.inputs, txn.outputs, jm)

    async def validate_with_task_and_queues(self):
        result = cryptoworker.get_txn_job_result()
        assert result is None
        task = create_task(cryptoworker.work())

        # do not save anything because this must all work with ephemeral data
        c0_1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 99999)
        c0_1.id = c0_1.generate_id(c0_1.data)
        c0_2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 11111)
        c0_2.id = c0_2.generate_id(c0_2.data)
        c1 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1111)
        c1.id = c1.generate_id(c1.data)
        c2 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 2222)
        c2.id = c2.generate_id(c2.data)
        c3 = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 3333)
        c3.id = c3.generate_id(c3.data)
        txn1 = models.Txn({
            'input_ids': c0_1.id,
            'output_ids': ','.join([c1.id, c2.id])
        })
        txn1.id = txn1.generate_id(txn1.data)
        txn1.inputs = [c0_1]
        txn1.outputs = [c1, c2]
        txn2 = models.Txn({
            'input_ids': c0_2.id,
            'output_ids': c3.id
        })
        txn2.id = txn2.generate_id(txn2.data)
        txn2.inputs = [c0_2]
        txn2.outputs = [c3]
        txn3 = models.Txn({
            'input_ids': '',
            'output_ids': ','.join([c1.id, c2.id])
        })
        txn3.id = txn3.generate_id(txn3.data)
        txn3.inputs = []
        txn3.outputs = [c1, c2]

        cryptoworker.submit_txn_job(txn1, debug='txn1 (2)')
        cryptoworker.submit_txn_job(txn2, debug='txn2 (2)')
        cryptoworker.submit_txn_job(txn3, debug='txn3 (2)')

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
        total_coins = 5
        cryptoworker.submit_mine_job(ANYONE_CAN_SPEND_LOCK.bytes, total_target, total_coins)
        result = run(cryptoworker.work_mine_job())
        assert type(result) is tuple
        assert len(result) == 2
        assert type(result[0]) is cryptoworker.JobMessage
        assert type(result[1]) is list
        assert len(result[1]) == total_coins, (len(result[1]), total_coins)
        jm, coins = result
        for c in coins:
            assert c.mint_value() >= c.amount, (c.mint_value(), c.amount)
        total_actual = sum([c.amount for c in coins])
        assert total_actual >= total_target

    async def mine_with_task_and_queues(self):
        task = create_task(cryptoworker.work())
        result = cryptoworker.get_mined_coins()
        assert result is None

        total_target = 555555
        total_coins = 5
        cryptoworker.submit_mine_job(ANYONE_CAN_SPEND_LOCK.bytes, total_target, total_coins)

        # wait for the jobs to complete
        await sleep(3)

        coins = cryptoworker.get_mined_coins()
        assert coins is not None
        assert type(coins) is list
        assert len(coins) == total_coins, (len(coins), total_coins)
        for c in coins:
            assert type(c) is models.Coin, (type(c), c)
            assert c.mint_value() >= c.amount, (c.mint_value(), c.amount)
        total_actual = sum([c.amount for c in coins])
        assert total_actual >= total_target

        # now test a job that raises an exception (mining less than min mint size)
        total_target = 555
        cryptoworker.submit_mine_job(ANYONE_CAN_SPEND_LOCK.bytes, total_target, 5)

        # wait for the jobs to complete
        await sleep(1)

        result = cryptoworker.get_mined_coins()
        assert result is not None
        assert type(result) is list
        for r in result:
            assert isinstance(r, Exception), type(r)

        task.cancel()

    def test_mine_with_task_and_queues(self):
        run(self.mine_with_task_and_queues())


if __name__ == '__main__':
    unittest.main()


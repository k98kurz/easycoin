from context import models, easycoin
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
SEED_PHRASE = ['test', 'obviously', 'not', 'secure']
PASSWORD = 'testp4ssword'
ANYONE_CAN_SPEND_LOCK = Script.from_src('true')


def automigrate():
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

def setup_class():
    models.Coin.connection_info = DB_FILEPATH
    models.Txn.connection_info = DB_FILEPATH
    models.Input.connection_info = DB_FILEPATH
    models.Output.connection_info = DB_FILEPATH
    models.Wallet.connection_info = DB_FILEPATH
    sqloquent.DeletedModel.connection_info = DB_FILEPATH
    if isfile(DB_FILEPATH):
        os.remove(DB_FILEPATH)
    automigrate()

def setup():
    models.Coin.query().delete()
    models.Txn.query().delete()
    models.Input.query().delete()
    models.Output.query().delete()
    models.Wallet.query().delete()


class TestInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_class()
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
        setup()
        super().setUp()

    def test_Input_relations_work(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD)
        w.save()
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1000)
        c.save()
        i = models.Input.insert({'id': c.id, 'wallet_id': w.id})
        w2 = i.wallet
        c2 = i.coin
        assert w2.id == w.id
        assert c2.id == c.id


class TestUTXOSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_class()
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
        setup()
        super().setUp()

    def test_can_apply_Txn_spending_existing_Output(self):
        u = easycoin.UTXOSet()
        t = models.Txn()
        o = models.Output.insert({'id': '1234'})
        t.input_ids = [o.id]
        assert u.can_apply(t)

    def test_apply_Txn_adds_Inputs_and_Outputs_to_database(self):
        u = easycoin.UTXOSet()
        coin = models.Coin.mine(ANYONE_CAN_SPEND_LOCK)
        coin.save()
        assert models.Input.query().count() == 0
        assert models.Output.query().count() == 0
        t = models.Txn()
        t.output_ids = [coin.id]
        u.apply(t)
        assert models.Input.query().count() == 0
        assert models.Output.query().count() == 1

    def test_can_reapply_existing_Output(self):
        u = easycoin.UTXOSet()
        t = models.Txn()
        o = models.Output.insert({'id': '1234'})
        t.output_ids = [o.id]
        assert u.can_apply(t)

    def test_can_reapply_Input_with_UTXOSet_before(self):
        u = easycoin.UTXOSet()
        # mint a new output
        o = models.Output.insert({'id': '1234'})
        t = models.Txn()
        t.output_ids = [o.id]
        assert u.can_apply(t)
        u.apply(t)
        # spend the coin
        t.output_ids = []
        t.input_ids = [o.id]
        assert u.can_apply(t)
        u.apply(t)
        # should not be able to re-spend the same coin
        assert not u.can_apply(t)
        # should be able to spend before the txn
        assert u.before(t).can_apply(t)

    def test_cannot_apply_spend_with_UTXOSet_after(self):
        u = easycoin.UTXOSet()
        # mint a new output
        o = models.Output.insert({'id': '1234'})
        t = models.Txn()
        t.output_ids = [o.id]
        assert u.can_apply(t)
        u.apply(t)
        # construct spend txn
        t.output_ids = []
        t.input_ids = [o.id]
        assert u.can_apply(t)
        assert not u.after(t).can_apply(t)


if __name__ == '__main__':
    unittest.main()


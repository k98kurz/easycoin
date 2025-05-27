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
        models.Input, models.Output, models.TrustNet,
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
    models.TrustNet.connection_info = DB_FILEPATH
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
    models.TrustNet.query().delete()
    models.Wallet.query().delete()


class TestUTXOClasses(unittest.TestCase):
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

    def test_Input_e2e(self):
        trustnet = models.TrustNet.insert({
            'name': 'Unit Test Net',
            'lock': ANYONE_CAN_SPEND_LOCK.bytes,
        })
        net_state = b'\x00' * 32
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1000, trustnet.id, net_state)
        c.save()
        i = models.Input.insert({
            'id': c.id,
            'net_id': c.net_id,
            'net_state': c.net_state,
            'commitment': c.commitment(c.data),
        })
        assert i.check()
        i.delete()
        i = models.Input.from_coin(c).save()
        assert i.check()
        packed = i.pack()
        assert len(packed) == 175, len(packed)
        unpacked = models.Input.unpack(packed)
        assert unpacked.id == i.id, (unpacked, i)
        assert unpacked.check()

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

    def test_Output_e2e(self):
        trustnet = models.TrustNet.insert({
            'name': 'Unit Test Net',
            'lock': ANYONE_CAN_SPEND_LOCK.bytes,
        })
        net_state = b'\x00' * 32
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1000, trustnet.id, net_state)
        c.save()
        o = models.Output.insert({
            'id': c.id,
            'net_id': c.net_id,
            'net_state': c.net_state,
            'commitment': c.commitment(c.data),
        })
        assert o.check()
        o.delete()
        o = models.Output.from_coin(c).save()
        assert o.check()
        packed = o.pack()
        assert len(packed) == 175, len(packed)
        unpacked = models.Output.unpack(packed)
        assert unpacked.id == o.id, (unpacked, o)
        assert unpacked.check()

    def test_Output_relations_work(self):
        w = models.Wallet.create(SEED_PHRASE, PASSWORD)
        w.save()
        c = models.Coin.create(ANYONE_CAN_SPEND_LOCK, 1000)
        c.save()
        o = models.Output.insert({'id': c.id, 'wallet_id': w.id})
        w2 = o.wallet
        c2 = o.coin
        assert w2.id == w.id
        assert c2.id == c.id

    def test_can_apply_Txn_spending_existing_Output(self):
        u = easycoin.UTXOSet()
        t = models.Txn()
        o = models.Output.insert({'id': '1234'})
        t.input_ids = [o.id]
        assert u.can_apply(t)

    def test_can_apply_Txn_spending_ephemeral_Output(self):
        u = easycoin.UTXOSet()
        oid = '1234'
        t = models.Txn({'output_ids': oid})
        u = u.after(t)
        t = models.Txn({'input_ids': oid})
        assert u.can_apply(t)

    def test_not_can_apply_Txn_spending_nonexistant_Output(self):
        u = easycoin.UTXOSet()
        oid = '1234'
        t = models.Txn({'input_ids': oid})
        assert not u.can_apply(t)

    def test_not_can_apply_Txn_spending_ephemerally_spent_Output(self):
        u = easycoin.UTXOSet()
        oid = '1234'
        o = models.Output.insert({'id': oid})
        t = models.Txn({'input_ids': oid})
        assert u.can_apply(t)
        u.add_inputs.add(oid)
        assert not u.can_apply(t)
        u.add_inputs.remove(oid)
        u.sub_outputs.add(oid)
        assert not u.can_apply(t)

    def test_not_can_apply_Txn_funding_spent_Input(self):
        u = easycoin.UTXOSet()
        oid = '1234'
        iid = '4321'
        models.Input.insert({'id': oid})
        t = models.Txn({'input_ids': iid, 'output_ids': oid})
        assert not u.can_apply(t)

    def test_apply_Txn_adds_Inputs_and_Outputs_to_database(self):
        u = easycoin.UTXOSet()
        coin = models.Coin.mine(ANYONE_CAN_SPEND_LOCK)
        coin.save()
        t = models.Txn()
        t.output_ids = [coin.id]

        assert models.Input.query().count() == 0
        assert models.Output.query().count() == 0
        u.apply(t)
        assert models.Input.query().count() == 0
        assert models.Output.query().count() == 1
        o = models.Output.query().first()
        assert not o.check()
        o.delete()

        assert models.Input.query().count() == 0
        assert models.Output.query().count() == 0
        u.apply(t, {coin.id: coin})
        assert models.Input.query().count() == 0
        assert models.Output.query().count() == 1
        o = models.Output.query().first()
        assert o.check()

    def test_can_reverse_Txn_with_existing_Inputs_and_Outputs(self):
        u = easycoin.UTXOSet()
        i = models.Input.insert({'id': '4321'})
        o = models.Output.insert({'id': '1234'})
        t = models.Txn({'input_ids': i.id, 'output_ids': o.id})
        assert u.can_reverse(t)

    def test_can_reverse_Txn_with_ephemeral_Inputs_and_Outputs(self):
        u = easycoin.UTXOSet()
        iid = '4321'
        oid = '1234'
        t = models.Txn({'input_ids': iid, 'output_ids': oid})
        assert u.after(t).can_reverse(t)

    def test_not_can_reverse_Txn_with_a_spent_Output(self):
        u = easycoin.UTXOSet()
        oid = '1234'
        models.Input.insert({'id': oid})
        t = models.Txn({'output_ids': oid})
        assert not u.can_reverse(t)

    def test_not_can_reverse_Txn_with_an_ephemerally_spent_Output(self):
        u = easycoin.UTXOSet()
        oid = '1234'
        t1 = models.Txn({'output_ids': oid})
        t2 = models.Txn({'input_ids': oid})
        assert not u.after(t2).can_reverse(t1)

    def test_reverse_Txn_undoes_apply_in_database(self):
        u = easycoin.UTXOSet()
        coin = models.Coin.mine(ANYONE_CAN_SPEND_LOCK)
        coin.save()
        t = models.Txn()
        t.output_ids = [coin.id]

        assert models.Input.query().count() == 0
        assert models.Output.query().count() == 0
        u.apply(t)
        assert models.Input.query().count() == 0
        assert models.Output.query().count() == 1

        u.reverse(t, {coin.id: coin})
        assert models.Input.query().count() == 0
        assert models.Output.query().count() == 0

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


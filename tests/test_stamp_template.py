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


def make_hashlock(preimage: bytes):
    return Script.from_src(
        f'sha256 push x{sha256(preimage).digest().hex()} equal'
    )


class TestStampTemplate(unittest.TestCase):
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
            models.Coin, models.StampTemplate,
            sqloquent.DeletedModel,
        ]:
            m.query().delete()
        super().setUp()

    def test_StampTemplate_setting_script_raises_errors(self):
        t = models.StampTemplate()
        # TypeError for non-dict input
        with self.assertRaises(TypeError):
            t.scripts = "not a dict"
        with self.assertRaises(TypeError):
            t.scripts = 123
        with self.assertRaises(TypeError):
            t.scripts = ["list", "of", "items"]
        # ValueError for invalid script keys
        with self.assertRaises(ValueError) as e:
            t.scripts = {'X': 'true'}
        assert 'scripts can only be' in str(e.exception).lower()
        with self.assertRaises(ValueError) as e:
            t.scripts = {'invalid': 'true'}
        # TypeError for non-string values
        with self.assertRaises(TypeError):
            t.scripts = {'L': 123}
        with self.assertRaises(TypeError):
            t.scripts = {'_': b'not a string'}
        with self.assertRaises(TypeError):
            t.scripts = {'$': ['list', 'of', 'strings']}
        # ValueError for invalid tapescript compilation
        with self.assertRaises(ValueError) as e:
            t.scripts = {'L': 'op_dup push'}
        assert 'Compilation error for L:' in str(e.exception)
        assert 'IndexError' in str(e.exception)
        with self.assertRaises(ValueError) as e:
            t.scripts = {'_': 'push x1234567890abcdef invalidopcode'}
        assert 'Compilation error for _:' in str(e.exception)
        assert 'SyntaxError' in str(e.exception)

    def test_type_property_handles_valid_and_invalid_inputs(self):
        t = models.StampTemplate()
        # test default value
        assert t.type == models.StampType.UNKNOWN
        # test valid models.StampType enum values
        t.type = models.StampType.SINGLE
        assert t.type == models.StampType.SINGLE
        t.type = models.StampType.TOKEN
        assert t.type == models.StampType.TOKEN
        t.type = models.StampType.UNKNOWN
        assert t.type == models.StampType.UNKNOWN
        # test valid str values
        t.type = 'single'
        assert t.type == models.StampType.SINGLE
        t.type = 'token'
        assert t.type == models.StampType.TOKEN
        t.type = 'unknown'
        assert t.type == models.StampType.UNKNOWN
        # test TypeError for invalid types
        with self.assertRaises(TypeError):
            t.type = 123
        with self.assertRaises(TypeError):
            t.type = ['list']
        with self.assertRaises(TypeError):
            t.type = None
        # test ValueError for invalid str values
        with self.assertRaises(ValueError):
            t.type = 'invalid'
        with self.assertRaises(ValueError):
            t.type = 'SINGLE'

    def test_details_property_handles_valid_and_invalid_inputs(self):
        t = models.StampTemplate()
        # test default value
        assert t.details is None
        # test valid dict
        t.details = {'name': 'test', 'value': 123}
        assert t.details == {'name': 'test', 'value': 123}
        # test None
        t.details = None
        assert t.details is None
        # test TypeError for invalid types
        with self.assertRaises(TypeError):
            t.details = "not a dict"
        with self.assertRaises(TypeError):
            t.details = 123
        with self.assertRaises(TypeError):
            t.details = ['list', 'of', 'items']

    def test_dsh_property_derives_consistent_hash(self):
        t = models.StampTemplate()
        # test return type is bytes
        assert type(t.dsh) is bytes
        assert len(t.dsh) == 32 # sha256 digest length
        # test consistency - same config produces same hash
        t1 = models.StampTemplate()
        t1.scripts = {'L': 'true', '_': 'false'}
        t1.details = {'name': 'test'}
        hash1 = t1.dsh
        hash2 = t1.dsh
        assert hash1 == hash2
        # test different scripts produce different hashes
        t2 = models.StampTemplate()
        t2.scripts = {'L': 'false', '_': 'true'}
        t2.details = {'name': 'test'}
        assert t1.dsh != t2.dsh
        # test different details produce different hashes
        t3 = models.StampTemplate()
        t3.scripts = {'L': 'true', '_': 'false'}
        t3.details = {'name': 'different'}
        assert t1.dsh != t3.dsh
        # test empty state handling
        t4 = models.StampTemplate()
        assert type(t4.dsh) is bytes
        assert len(t4.dsh) == 32
        # test empty scripts with details
        t5 = models.StampTemplate()
        t5.details = {'name': 'test'}
        assert type(t5.dsh) is bytes
        assert len(t5.dsh) == 32


if __name__ == '__main__':
    unittest.main()


from context import models, easycoin
import unittest


class TestMisc(unittest.TestCase):
    def test_wordlist(self):
        assert type(easycoin.wordlist()) is tuple
        assert all([type(l) is str for l in easycoin.wordlist()])
        assert len(easycoin.wordlist()) == 2048


if __name__ == '__main__':
    unittest.main()


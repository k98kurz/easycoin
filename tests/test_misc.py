from context import models, easycoin
import unittest


class TestMisc(unittest.TestCase):
    def test_wordlist(self):
        assert type(easycoin.wordlist()) is tuple
        assert all([type(l) is str for l in easycoin.wordlist()])
        assert len(easycoin.wordlist()) == 2048

    def test_TrustNetFeatures(self):
        features = {
            easycoin.TrustNetFeature.SNAPSHOT_OUTPUTS,
            easycoin.TrustNetFeature.LOCK_SNAPSHOT,
        }
        flag = easycoin.TrustNetFeature.make_flag(features)
        assert type(flag) is int
        assert flag == 9
        parsed = easycoin.TrustNetFeature.parse_flag(flag)
        assert parsed == features, (parsed, features)

        # flag of 65535 should have all features
        flag_all = 2**16-1
        parsed = easycoin.TrustNetFeature.parse_flag(flag_all)
        for val in easycoin.TrustNetFeature:
            assert val in parsed


if __name__ == '__main__':
    unittest.main()


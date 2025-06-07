from __future__ import annotations
from enum import IntEnum


class TrustNetFeature(IntEnum):
    SNAPSHOT_OUTPUTS = 1
    SNAPSHOT_INPUTS = 2
    SNAPSHOT_TXNS = 4
    SNAPSHOT_PROOFS = 8
    SNAPSHOT_MUTATIONS = 16
    LOCK_SNAPSHOT = 32
    LOCK_ATTEST = 64
    LOCK_CONFIRM = 128
    LOCK_MEMBERS = 256
    RESERVED9 = 512
    RESERVED10 = 1024

    @classmethod
    def make_flag(cls, features: set[TrustNetFeature]) -> int:
        flag = 0
        for f in features:
            flag |= f.value
        return flag

    @classmethod
    def parse_flag(cls, flags: int = 0) -> set[TrustNetFeature]:
        features = set()
        for val in cls:
            if flags & val.value:
                features.add(val)
        return features



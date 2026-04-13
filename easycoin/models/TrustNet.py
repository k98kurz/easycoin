from __future__ import annotations
from easycoin.errors import type_assert, value_assert
from .TrustNetFeature import TrustNetFeature
from merkleasy import Tree
from sqloquent import HashedModel, RelatedCollection
import packify


class TrustNet(HashedModel):
    connection_info: str = ''
    table: str = 'trust_nets'
    id_column: str = 'id'
    columns: tuple[str] = (
        'id', 'name', 'lock', 'params', 'delegate_scripts', 'root', 'members',
        'quorum', 'root_witness', 'active', 'state'
    )
    columns_excluded_from_hash = (
        'delegate_scripts', 'root', 'members', 'quorum', 'root_witness', 'active',
        'state'
    )
    id: str
    name: str
    lock: bytes
    params: bytes
    delegate_scripts: bytes|None
    root: bytes|None
    members: bytes|None
    quorum: int|None
    root_witness: bytes|None
    active: bool
    state: bytes|None
    coins: RelatedCollection
    snapshots: RelatedCollection
    outputs: RelatedCollection
    inputs: RelatedCollection

    @property
    def id_bytes(self) -> bytes:
        return bytes.fromhex(self.id)

    @property
    def params(self) -> dict:
        if not self.data.get('params', None):
            return {}
        return packify.unpack(self.data['params'])
    @params.setter
    def params(self, val: dict):
        type_assert(type(val) is dict, 'params must be a dict')
        self.data['params'] = packify.pack(val)

    @property
    def delegate_scripts(self) -> dict:
        if not self.data.get('delegate_scripts', None):
            return {}
        return packify.unpack(self.data['delegate_scripts'])
    @delegate_scripts.setter
    def delegate_scripts(self, val: dict[str, bytes]):
        type_assert(type(val) is dict,
            'delegate_scripts must be dict[str, bytes]')
        for k, v in val.items():
            type_assert(type(k) is str,
                'delegate_scripts must be dict[str, bytes]')
            type_assert(type(v) is bytes,
                'delegate_scripts must be dict[str, bytes]')
        self.data['delegate_scripts'] = packify.pack(val)

    @property
    def features(self) -> set[TrustNetFeature]:
        return TrustNetFeature.parse_flag(self.params.get('features', 0))
    @features.setter
    def features(self, val: int|set[TrustNetFeature]):
        type_assert(type(val) in (int, set),
            'features must be int|set[TrustNetFeature]')
        if type(val) is int:
            self.params = {**self.params, 'features': val}
            return
        type_assert(all([type(v) is TrustNetFeature for v in val]),
            'features must be int|set[TrustNetFeature]')
        self.params = {**self.params, 'features': TrustNetFeature.make_flag(val)}

    @property
    def members(self) -> list[bytes]:
        if self.data.get('members', None):
            return packify.unpack(self.data['members'])
        return []
    @members.setter
    def members(self, val: list[bytes]):
        type_assert(isinstance(val, list),
            'members must be list[bytes] (list of tapescript bytecode locks)')
        type_assert(all([isinstance(v, bytes) for v in val]),
            'members must be list[bytes] (list of tapescript bytecode locks)')

        members = sorted(val)
        self.data['members'] = packify.pack(members)
        self.data['root'] = Tree.from_leaves(members).root

    @property
    def root(self) -> bytes|None:
        return self.data.get('root', None)

    def pack(self) -> bytes:
        """Serialize public info to bytes for transmission across the network."""
        data = {
            k: v
            for k, v in self.data.items()
            if k in self.columns and k not in self.columns_excluded_from_hash
        }
        return packify.pack(data)

    @classmethod
    def unpack(cls, data: bytes) -> TrustNet:
        """Deserialize info from bytes."""
        return cls(packify.unpack(data))


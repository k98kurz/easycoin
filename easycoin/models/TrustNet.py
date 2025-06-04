from .errors import type_assert, value_assert
from .TrustNetFeature import TrustNetFeature
from merkleasy import Tree
from sqloquent import HashedModel, RelatedCollection
import packify


class TrustNet(HashedModel):
    connection_info: str = ''
    table: str = 'trust_nets'
    id_column: str = 'id'
    columns: tuple[str] = (
        'id', 'name', 'lock', 'params', 'delegate_script', 'root', 'members', 'quorum',
        'root_witness', 'active'
    )
    columns_excluded_from_hash = (
        'delegate_script', 'root', 'members', 'quorum', 'root_witness', 'active'
    )
    id: str
    name: str
    lock: bytes
    params: bytes
    delegate_script: bytes|None
    root: bytes|None
    members: bytes|None
    quorum: int|None
    root_witness: bytes|None
    active: bool
    coins: RelatedCollection
    snapshots: RelatedCollection
    outputs: RelatedCollection
    inputs: RelatedCollection

    @property
    def params(self) -> dict:
        if not self.data.get('params', None):
            return {}
        return packify.unpack(self.data['params'])

    @property
    def features(self) -> set[TrustNetFeature]:
        return TrustNetFeature.parse_flag(self.params.get('features', 0))

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



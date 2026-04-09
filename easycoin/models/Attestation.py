from .Coin import Coin
from .TrustNet import TrustNet
from .TrustNetFeature import TrustNetFeature
from easycoin.errors import type_assert, value_assert
from sqloquent import HashedModel, RelatedModel, RelatedCollection
import packify


_empty_list = packify.pack([])


class Attestation(HashedModel):
    connection_info: str = ''
    table: str = 'attestations'
    id_column: str = 'id'
    columns: tuple[str] = ('id', 'txn_id', 'input_ids', 'output_ids', 'witness')
    id: str
    txn_id: str|None
    input_ids: str|None
    output_ids: str|None
    witness: bytes
    txn: RelatedModel
    inputs: RelatedCollection
    outputs: RelatedCollection

    @property
    def input_ids(self) -> list[str]:
        return self.data.get('input_ids', '').split(',')
    @input_ids.setter
    def input_ids(self, val: list[str]):
        type_assert(type(val) is list, 'input_ids must be list[str] of ids')
        type_assert(all([type(v) is list for v in val]),
            'input_ids must be list[str] of ids')
        val.sort()
        self.data['input_ids'] = ','.join(val)

    @property
    def output_ids(self) -> list[str]:
        return self.data.get('output_ids', '').split(',')
    @output_ids.setter
    def output_ids(self, val: list[str]):
        type_assert(type(val) is list, 'output_ids must be list[str] of ids')
        type_assert(all([type(v) is list for v in val]),
            'output_ids must be list[str] of ids')
        val.sort()
        self.data['output_ids'] = ','.join(val)

    def runtime_cache(self) -> dict:
        """Return the tapescript runtime cache."""
        return {
            "sigfield1": b'Attest',
            "sigfield2": bytes.fromhex(self.txn_id or ''),
            "sigfield3": packify.pack(self.input_ids),
            "sigfield4": packify.pack(self.output_ids),
        }

    def validate(self, net_id: str|None = None, reload: bool = True) -> bool:
        """Runs Attestation validation logic. Returns False if the witness
            data does not validate against the/a relevant TrustNet lock.
            If `net_id` is not specified, this will return True if the
            lock of the TrustNet from any input or output is satisfied
            by the witness; if it is specified, it will require that
            specific TrustNet lock must be satisfied.
        """
        if reload:
            self.inputs().reload()
            self.outputs().reload()
        if net_id:
            trustnet = TrustNet.find(net_id)
            lock = b''
            if TrustNetFeature.LOCK_ATTEST in trustnet.features:
                lock = trustnet.lock
            return run_auth_scripts([self.witness, lock], self.runtime_cache())

        # get all related trustnets
        trustnets = {}
        for i in self.inputs:
            i.trustnet().reload() if reload else 0
            if i.trustnet:
                trustnets[i.trustnet.id] = i.trustnet
        for o in self.outputs:
            o.trustnet().reload() if reload else 0
            if o.trustnet:
                trustnets[o.trustnet.id] = o.trustnet

        # return True if any trustnet lock is satisfied
        cache = self.runtime_cache()
        for _, net in trustnets.items():
            if run_auth_scripts([self.witness, net.lock], cache):
                return True
        return False


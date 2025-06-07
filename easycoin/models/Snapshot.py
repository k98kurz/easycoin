from .TrustNetFeature import TrustNetFeature
from sqloquent import HashedModel, RelatedCollection, RelatedModel
from tapescript import run_auth_scripts
import packify


class Snapshot(HashedModel):
    connection_info: str = ''
    table: str = 'snapshots'
    id_column: str = 'id'
    columns: tuple[str] = (
        'id', 'net_id', 'params', 'timestamp', 'state', 'chunk_ids',
        'witness'
    )
    id: str
    net_id: str
    params: bytes
    timestamp: int
    state: bytes
    chunk_ids: str|None
    witness: bytes
    trustnet: RelatedModel
    chunks: RelatedCollection

    @property
    def chunk_ids_bytes(self) -> list[bytes]:
        if not self.chunk_ids:
            return []
        return [bytes.fromhex(cid) for cid in self.chunk_ids.split(',')]

    def calculate_state(self) -> bytes:
        """Calculates the state commitment of the snapshot."""
        return sha256(packify.pack({
            'net_id': self.net_id,
            'params': self.params,
            'timestamp': self.timestamp,
            'chunk_ids': self.chunk_ids_bytes,
        })).digest()

    def runtime_cache(self) -> dict:
        """Return the tapescript runtime cache."""
        return {
            "sigfield1": b'Snapshot',
            "sigfield2": self.calculate_state(),
        }

    def validate(self, reload: bool = True) -> bool:
        """Runs Snapshot validation logic. Returns False if the witness
            data does not validate against the TrustNet lock.
        """
        if reload:
            self.trustnet().reload()
        lock = b''
        if TrustNetFeature.LOCK_SNAPSHOT in self.trustnet.features:
            lock = trustnet.lock
        return run_auth_scripts([self.witness, lock], self.runtime_cache())


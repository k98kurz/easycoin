from __future__ import annotations
from easycoin.errors import type_assert
from .TrustNetFeature import TrustNetFeature
from hashlib import sha256
from sqloquent import HashedModel, RelatedCollection, RelatedModel
from tapescript import Script, run_auth_scripts
from time import time
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

    @classmethod
    def create(
            cls, net_id: str, chunks: list[str] = [], params: bytes = b'',
            timestamp: int = 0
        ) -> Snapshot:
        """"""
        type_assert(type(net_id) is str, 'net_id must be str')
        type_assert(type(chunks) is list, 'chunks must be list[str]')
        type_assert(all([type(c) is str for c in chunks]),
            'chunks must be list[str]')
        type_assert(type(params) is bytes, 'params must be bytes')
        type_assert(type(timestamp) is int, 'timestamp must be int')
        snapshot = cls({
            'net_id': net_id,
            'params': params,
            'timestamp': timestamp or int(time()),
            'chunk_ids': ','.join(chunks),
        })
        snapshot.state = snapshot.calculate_state()
        return snapshot

    def calculate_state(self) -> bytes:
        """Calculates the state commitment of the snapshot."""
        return sha256(packify.pack([
            self.net_id,
            self.params,
            self.timestamp,
            self.chunk_ids_bytes,
        ])).digest()

    def runtime_cache(self) -> dict:
        """Return the tapescript runtime cache."""
        return {
            "sigfield1": b'Snapshot',
            "sigfield2": self.calculate_state(),
        }

    def validate(self, reload: bool = True, debug: str|bool = False) -> bool:
        """Runs Snapshot validation logic. Returns False if the witness
            data does not validate against the TrustNet lock.
        """
        if reload:
            print(f'{debug}: reloading trustnet') if debug else ''
            self.trustnet().reload()
        lock = b''
        if TrustNetFeature.LOCK_SNAPSHOT in self.trustnet.features:
            print(f'{debug}: LOCK_SNAPSHOT - replacing lock') if debug else ''
            lock = self.trustnet.lock
        if debug:
            print(f'{debug}: run_auth_scripts([')
            print(Script.from_bytes(self.witness).src)
            print(Script.from_bytes(lock).src)
            print('])')
        return run_auth_scripts([self.witness, lock], self.runtime_cache())


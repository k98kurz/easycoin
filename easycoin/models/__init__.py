from .Coin import Coin
from .Txn import Txn
from .Wallet import Wallet
from .Input import Input
from .Output import Output
from .TrustNet import TrustNet
from .TrustNetFeature import TrustNetFeature
from .Attestation import Attestation
from .Confirmation import Confirmation
from .Snapshot import Snapshot
from .Chunk import Chunk, ChunkKind
from sqloquent import contains, within, belongs_to, has_many, has_one, DeletedModel
from typing import Callable
import sqloquent.tools


def set_connection_info(db_file_path: str):
    """Set the connection info for all models to use the specified
        sqlite3 database file path.
    """
    models = [
        Coin, Txn, Wallet, Input, Output,
        TrustNet, Attestation, Confirmation, Snapshot, Chunk,
        DeletedModel,
    ]
    for m in models:
        m.connection_info = db_file_path

def get_migrations() -> dict[str, str]:
    """Returns a dict mapping model names to migration file content strs."""
    models = [
        Coin, Txn, Wallet, Input, Output,
        TrustNet, Attestation, Confirmation, Snapshot, Chunk,
    ]
    migrations = {}
    for model in models:
        migrations[model.__name__] = sqloquent.tools.make_migration_from_model(model)

    migrations['Coin'] = migrations['Coin'].replace(
        "('details').nullable().index()", "('details').nullable()"
    )

    migrations['Txn'] = migrations['Txn'].replace(
        "('details').nullable().index()", "('details').nullable()"
    )
    migrations['Txn'] = migrations['Txn'].replace(
        "('witness').nullable().index()", "('witness').nullable()"
    )

    migrations['Wallet'] = migrations['Wallet'].replace(
        "('seed').index()", "('seed')"
    )
    migrations['Wallet'] = migrations['Wallet'].replace(
        "('checksum').index()", "('checksum')"
    )
    migrations['Wallet'] = migrations['Wallet'].replace(
        "('nonce').default(0).index()", "('nonce').default(0)"
    )
    migrations['Wallet'] = migrations['Wallet'].replace(
        "('pubkeys').nullable().index()", "('pubkeys').nullable()"
    )
    migrations['Wallet'] = migrations['Wallet'].replace(
        "('secrets').index()", "('secrets')"
    )

    migrations['Input'] = migrations['Input'].replace(
        "('commitment').nullable().index()", "('commitment').nullable()"
    )

    migrations['Output'] = migrations['Output'].replace(
        "('commitment').nullable().index()", "('commitment').nullable()"
    )

    migrations['TrustNet'] = migrations['TrustNet'].replace(
        "('lock').index()", "('lock')"
    )
    migrations['TrustNet'] = migrations['TrustNet'].replace(
        "('params').index()", "('params')"
    )
    migrations['TrustNet'] = migrations['TrustNet'].replace(
        "('delegate_scripts').nullable().index()",
        "('delegate_scripts').nullable()"
    )
    migrations['TrustNet'] = migrations['TrustNet'].replace(
        "('root').nullable().index()", "('root').nullable()"
    )
    migrations['TrustNet'] = migrations['TrustNet'].replace(
        "('members').nullable().index()", "('members').nullable()"
    )
    migrations['TrustNet'] = migrations['TrustNet'].replace(
        "('quorum').nullable().index()", "('quorum').nullable()"
    )
    migrations['TrustNet'] = migrations['TrustNet'].replace(
        "('root_witness').nullable().index()", "('root_witness').nullable()"
    )
    migrations['TrustNet'] = migrations['TrustNet'].replace(
        "('active').index()", "('active')"
    )

    migrations['Attestation'] = migrations['Attestation'].replace(
        "blob('witness').index()", "blob('witness')"
    )

    migrations['Confirmation'] = migrations['Confirmation'].replace(
        "blob('witness').index()", "blob('witness')"
    )

    migrations['Snapshot'] = migrations['Snapshot'].replace(
        "('witness').index()", "('witness')"
    )

    migrations['Snapshot'] = migrations['Snapshot'].replace(
        "('params').index()", "('params')"
    )

    migrations['Chunk'] = migrations['Chunk'].replace(
        "('root').index()", "('root')"
    )
    migrations['Chunk'] = migrations['Chunk'].replace(
        "('leaves').index()", "('leaves')"
    )

    return migrations

def publish_migrations(
        migration_folder_path: str,
        migration_callback: Callable[[str, str], str] = None
    ):
    """Writes migration files for the models. If a migration callback is
        provided, it will be used to modify the migration file contents.
        The migration callback will be called with the model name and
        the migration file contents, and whatever it returns will be
        used as the migration file contents.
    """
    sqloquent.tools.publish_migrations(migration_folder_path)
    migrations = get_migrations()
    for name, m in migrations.items():
        m2 = migration_callback(name, m) if migration_callback else m
        m = m2 if type(m2) is str and len(m2) > 0 else m
        with open(f'{migration_folder_path}/create_{name}.py', 'w') as f:
            f.write(m)

def automigrate(migration_folder_path: str, db_file_path: str):
    """Executes the sqloquent automigrate tool."""
    sqloquent.tools.automigrate(migration_folder_path, db_file_path)


# define relations
Coin.origins = within(Coin, Txn, 'output_ids')
Coin.spends = within(Coin, Txn, 'input_ids')
Coin.wallet = belongs_to(Coin, Wallet, 'wallet_id')
Coin.trustnet = belongs_to(Coin, TrustNet, 'net_id')

Txn.inputs = contains(Txn, Coin, 'input_ids')
Txn.outputs = contains(Txn, Coin, 'output_ids')
Txn.wallet = belongs_to(Txn, Wallet, 'wallet_id')
Txn.attestations = has_many(Txn, Attestation, 'txn_id')
Txn.confirmation = has_one(Txn, Confirmation, 'txn_id')

Wallet.txns = has_many(Wallet, Txn, 'wallet_id')
Wallet.coins = has_many(Wallet, Coin, 'wallet_id')
Wallet.inputs = has_many(Wallet, Input, 'wallet_id')
Wallet.outputs = has_many(Wallet, Output, 'wallet_id')

Input.coin = belongs_to(Input, Coin, 'id')
Input.wallet = belongs_to(Input, Wallet, 'wallet_id')
Input.trustnet = belongs_to(Input, TrustNet, 'net_id')
Input.attestations = within(Input, Attestation, 'input_ids')
Input.confirmations = within(Input, Confirmation, 'input_ids')

Output.coin = belongs_to(Output, Coin, 'id')
Output.wallet = belongs_to(Output, Wallet, 'wallet_id')
Output.trustnet = belongs_to(Output, TrustNet, 'net_id')
Output.attestations = within(Output, Attestation, 'output_ids')
Output.confirmations = within(Output, Confirmation, 'output_ids')

TrustNet.coins = has_many(TrustNet, Coin, 'net_id')
TrustNet.snapshots = has_many(TrustNet, Snapshot, 'net_id')
TrustNet.outputs = has_many(TrustNet, Output, 'net_id')
TrustNet.inputs = has_many(TrustNet, Input, 'net_id')

Attestation.txn = belongs_to(Attestation, Txn, 'txn_id')
Attestation.inputs = contains(Attestation, Input, 'input_ids')
Attestation.outputs = contains(Attestation, Output, 'output_ids')

Snapshot.trustnet = belongs_to(Snapshot, TrustNet, 'net_id')
Snapshot.chunks = contains(Snapshot, Chunk, 'chunk_ids')

Chunk.trustnet = belongs_to(Chunk, TrustNet, 'net_id')
Chunk.snapshots = within(Chunk, Snapshot, 'chunk_ids')
Chunk.parents = contains(Chunk, Chunk, 'parent_ids')
Chunk.children = within(Chunk, Chunk, 'parent_ids')


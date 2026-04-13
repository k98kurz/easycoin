# easycoin.gameset

This module provides tools for creating and applying GameSets, which are zip
files containing packed exports of Txn, Coin, Input, and Output database tables.
Each table is exported as a folder containing individual files where the
filename is the object ID and the content is the packed bytes.

## Functions

### `create_gameset(output_filename: str) -> str:`

Create a GameSet ZIP file containing packed exports of Txn, Coin, Input, and
Output tables. Each table is exported as a folder containing individual files
where the filename is the object ID and the content is the packed bytes. Empty
tables are skipped entirely. Raises `TypeError` or `ValueError` for invalid
parameters.

### `calculate_gameset_hash(gameset_path: str) -> str:`

Calculate the SHA256 hash of a GameSet ZIP file for UI verification. Returns:
hex string of hash with checksum (72 chars total: 64 for SHA256 + 8 for 4-byte
checksum).

### `apply_gameset(gameset_path: str, db_filepath: str, migrations_path: str, backup_path: str | None = None):`

Apply a GameSet ZIP file to restore a database. Backs up the existing database
if present, truncates the GameSet tables, then imports packed data from the
GameSet. The workflow: validate → backup → truncate tables → extract → import
packed files → cleanup. Empty folders are skipped. Raises `TypeError` or
`ValueError` for invalid parameters.

### `validate_gameset_hash(gameset_hash: str) -> bool:`

Validate a Game Set hash with checksum. Similar pattern to Address.validate().
The hash is SHA256 (64 hex chars) + 4 byte checksum (8 hex chars) for a total of
72 hex characters. Returns `False` if validation fails.



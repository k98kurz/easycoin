"""
This module provides tools for creating and applying GameSets, which are
zip files containing packed exports of Txn, Coin, Input, and Output database
tables. Each table is exported as a folder containing individual files
where the filename is the object ID and the content is the packed bytes.
"""

from os import listdir, makedirs, path, remove, rmdir
from hashlib import sha256
from io import StringIO
from os import listdir, makedirs, path, remove, rmdir
from shutil import copy2, rmtree
from tempfile import mkdtemp
from time import time
from zipfile import ZIP_DEFLATED, ZipFile
from genericpath import isfile, isdir
from sqloquent import SqlModel
from easycoin.errors import type_assert, value_assert
from easycoin.models import (
    Coin, Input, Output, Txn,
    publish_migrations, automigrate
)


def _export_model_to_folder(
        model_class: type[SqlModel],
        folder_name: str,
        base_dir: str
    ) -> list[str]:
    """Export a model's database table to a folder with individual files.
        Each file is named after the object ID and contains the packed bytes.
        Returns: list of created file paths (empty if table is empty).
    """
    records = model_class.query().get()

    if not records:
        return []

    folder_path = path.join(base_dir, folder_name)
    makedirs(folder_path, exist_ok=True)

    file_paths: list[str] = []
    for record in records:
        if hasattr(record, 'pack_for_gameset'):
            packed_data = record.pack_for_gameset()
        else:
            packed_data = record.pack()
        file_path = path.join(folder_path, record.id)
        with open(file_path, 'wb') as f:
            f.write(packed_data)
        file_paths.append(file_path)

    return file_paths


def _import_model_from_folder(
        folder_path: str,
        model_class: type[SqlModel]
    ) -> None:
    """Import packed data from a folder to a database table.
        Each file is unpacked and saved, preserving the original ID.
        Raises `ValueError` for invalid data or corrupt files.
    """
    type_assert(isinstance(folder_path, str), 'folder_path must be str')
    type_assert(isinstance(model_class, type), 'model_class must be type')
    value_assert(isdir(folder_path),
        f'folder_path must be valid directory: {folder_path}')

    for file_name in listdir(folder_path):
        file_path = path.join(folder_path, file_name)
        if isfile(file_path):
            with open(file_path, 'rb') as f:
                packed_data = f.read()

            try:
                obj = model_class.unpack(packed_data)
                obj.save()
            except Exception as e:
                raise ValueError(
                    f"Failed to import {model_class.__name__} from file "
                    f"'{file_name}': {e}"
                ) from e


def create_gameset(output_filename: str) -> str:
    """Create a GameSet ZIP file containing packed exports of Txn,
        Coin, Input, and Output tables.
        Each table is exported as a folder containing individual files
        where the filename is the object ID and the content is the packed bytes.
        Empty tables are skipped entirely.
        Raises `TypeError` or `ValueError` for invalid parameters.
    """
    type_assert(isinstance(output_filename, str),
        'output_filename must be str')
    value_assert(len(output_filename) > 0,
        'output_filename must not be empty')

    temp_dir = mkdtemp()
    try:
        txn_files = _export_model_to_folder(Txn, 'txns', temp_dir)
        coin_files = _export_model_to_folder(Coin, 'coins', temp_dir)
        input_files = _export_model_to_folder(Input, 'inputs', temp_dir)
        output_files = _export_model_to_folder(Output, 'outputs', temp_dir)

        all_files = txn_files + coin_files + input_files + output_files
        value_assert(len(all_files) > 0,
            'all tables are empty, cannot create empty GameSet')

        with ZipFile(output_filename, 'w', ZIP_DEFLATED) as zip_file:
            for file_path in all_files:
                arcname = path.relpath(file_path, temp_dir)
                zip_file.write(file_path, arcname)

        return output_filename
    finally:
        rmtree(temp_dir, ignore_errors=True)


def calculate_gameset_hash(gameset_path: str) -> str:
    """Calculate the SHA256 hash of a GameSet ZIP file for UI
        verification. Returns: hex string of hash with checksum (72
        chars total: 64 for SHA256 + 8 for 4-byte checksum).
    """
    type_assert(isinstance(gameset_path, str), 'gameset_path must be str')
    value_assert(isfile(gameset_path),
        f'gameset_path must be valid file: {gameset_path}')

    hash_obj = sha256()
    with open(gameset_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_obj.update(chunk)
    hash_hex = hash_obj.hexdigest()
    checksum = sha256(bytes.fromhex(hash_hex)).digest()[:4].hex()
    return hash_hex + checksum


def _backup_database(db_filepath: str, backup_path: str | None = None) -> str | None:
    """Backup existing database file. If backup_path is None, generates
        '{timestamp}.easycoin.db-backup'. Returns: path to backup file
        or None if database doesn't exist.
    """
    type_assert(isinstance(db_filepath, str), 'db_filepath must be str')
    type_assert(backup_path is None or isinstance(backup_path, str),
        'backup_path must be None or str')

    if not isfile(db_filepath):
        return None

    if backup_path is None:
        timestamp = str(int(time()))
        backup_path = f"{timestamp}.easycoin.db-backup"
        backup_dir = path.dirname(db_filepath)
        if backup_dir:
            backup_path = path.join(backup_dir, backup_path)

    copy2(db_filepath, backup_path)
    return backup_path


def apply_gameset(
        gameset_path: str,
        db_filepath: str,
        migrations_path: str,
        backup_path: str | None = None,
    ) -> None:
    """Apply a GameSet ZIP file to restore a database. Backs up the
        existing database if present, truncates the GameSet tables, then imports
        packed data from the GameSet.
        The workflow: validate → backup → truncate tables → extract →
        import packed files → cleanup. Empty folders are skipped.
        Raises `TypeError` or `ValueError` for invalid parameters.
    """
    type_assert(isinstance(gameset_path, str), 'gameset_path must be str')
    type_assert(isinstance(db_filepath, str), 'db_filepath must be str')
    type_assert(isinstance(migrations_path, str), 'migrations_path must be str')
    type_assert(backup_path is None or isinstance(backup_path, str),
        'backup_path must be None or str')
    value_assert(len(gameset_path) > 0, 'gameset_path must not be empty')
    value_assert(len(db_filepath) > 0, 'db_filepath must not be empty')
    value_assert(len(migrations_path) > 0, 'migrations_path must not be empty')
    value_assert(isfile(gameset_path),
        f'gameset_path must be valid file: {gameset_path}')
    value_assert(isdir(migrations_path),
        f'migrations_path must be valid directory: {migrations_path}')

    _backup_database(db_filepath, backup_path)

    Input.query().execute_raw(f'delete from {Input.table}')
    Output.query().execute_raw(f'delete from {Output.table}')
    Coin.query().execute_raw(f'delete from {Coin.table}')
    Txn.query().execute_raw(f'delete from {Txn.table}')

    temp_dir = mkdtemp()
    try:
        with ZipFile(gameset_path, 'r') as zip_file:
            zip_file.extractall(temp_dir)

        folder_mapping = {
            'txns': Txn,
            'coins': Coin,
            'inputs': Input,
            'outputs': Output,
        }

        for folder_name, model_class in folder_mapping.items():
            folder_path = path.join(temp_dir, folder_name)
            if isdir(folder_path):
                try:
                    _import_model_from_folder(folder_path, model_class)
                except ValueError as e:
                    raise ValueError(
                        f"Failed to import from {folder_name} folder: {e}"
                    ) from e
    finally:
        rmtree(temp_dir, ignore_errors=True)


def validate_gameset_hash(gameset_hash: str) -> bool:
    """Validate a Game Set hash with checksum. Similar pattern to
        Address.validate(). The hash is SHA256 (64 hex chars) + 4 byte
        checksum (8 hex chars) for a total of 72 hex characters.
        Returns `False` if validation fails.
    """
    type_assert(type(gameset_hash) is str, 'gameset_hash must be str')

    if len(gameset_hash) != 72:
        return False

    try:
        hash_bytes = bytes.fromhex(gameset_hash[:64])
        checksum_bytes = bytes.fromhex(gameset_hash[64:])
    except ValueError:
        return False

    return sha256(hash_bytes).digest()[:4] == checksum_bytes

"""
This module provides tools for creating and applying GameSets, which are
zip files containing CSV exports of Txn, Coin, Input, and Output database
tables.
"""

from csv import reader, writer
from hashlib import sha256
from io import StringIO
from os import listdir, makedirs, path, remove, rmdir
from shutil import copy2
from tempfile import mkdtemp
from time import time
from typing import TYPE_CHECKING, get_args, get_origin
from zipfile import ZIP_DEFLATED, ZipFile
from genericpath import isfile, isdir
from sqloquent import SqlModel, Default
from easycoin.errors import type_assert, value_assert
from easycoin.helpers import create_temp_file
from easycoin.models import (
    Coin, Input, Output, Txn,
    publish_migrations, automigrate
)


def _prepare_value_for_csv(value: any) -> any:
    """Prepare a value for CSV export. Converts bytes to hex,
        handles None values.
    """
    if value is None:
        return '~None~'
    if isinstance(value, bytes):
        return value.hex()
    return value


def _export_model_to_csv(
        model_class: type[SqlModel],
        csv_filename: str,
        chunk_size: int = 500
    ) -> str | None:
    """Export a model's database table to CSV. Returns: path to
        CSV file or None if table is empty.
    """
    records = model_class.query().get()
    excluded_columns = ['wallet_id', 'key_index1', 'key_index2']

    if not records:
        return None

    fieldnames = model_class.columns
    fieldnames = [field for field in fieldnames if field not in excluded_columns]

    csv_buffer = StringIO()
    csv_writer = writer(csv_buffer)
    csv_writer.writerow(fieldnames)

    for record in records:
        row_values = [
            _prepare_value_for_csv(record.data.get(field))
            for field in fieldnames
        ]
        csv_writer.writerow(row_values)

    csv_content = csv_buffer.getvalue().encode('utf-8')
    csv_path = create_temp_file(csv_content, csv_filename)

    return csv_path


def _create_zip_from_files(file_paths: list[str], output_filename: str) -> str:
    """Create a ZIP archive from multiple files and save to the
        specified path. Returns: path to created ZIP file.
    """
    type_assert(isinstance(output_filename, str),
        'output_filename must be str')
    value_assert(len(output_filename) > 0,
        'output_filename must not be empty')

    with ZipFile(output_filename, 'w', ZIP_DEFLATED) as zip_file:
        for file_path in file_paths:
            if path.exists(file_path):
                basename = path.basename(file_path)
                if basename.startswith('easycoin_'):
                    basename = basename[9:]
                zip_file.write(file_path, basename)

    return output_filename


def create_gameset(output_filename: str, chunk_size: int = 500) -> str:
    """Create a GameSet ZIP file containing CSV exports of Txn,
        Coin, Input, and Output tables.

        The CSV files are created as temporary files and then
        bundled into a ZIP archive saved to specified path.
        Empty tables are skipped entirely.

        Raises `TypeError` or `ValueError` for invalid parameters.
    """
    type_assert(isinstance(output_filename, str),
        'output_filename must be str')
    type_assert(isinstance(chunk_size, int) and chunk_size > 0,
        'chunk_size must be positive int')
    value_assert(len(output_filename) > 0,
        'output_filename must not be empty')

    csv_paths: list[str] = []

    txn_csv_path = _export_model_to_csv(Txn, 'txns.csv', chunk_size)
    if txn_csv_path:
        csv_paths.append(txn_csv_path)

    coin_csv_path = _export_model_to_csv(Coin, 'coins.csv', chunk_size)
    if coin_csv_path:
        csv_paths.append(coin_csv_path)

    input_csv_path = _export_model_to_csv(Input, 'inputs.csv', chunk_size)
    if input_csv_path:
        csv_paths.append(input_csv_path)

    output_csv_path = _export_model_to_csv(Output, 'outputs.csv', chunk_size)
    if output_csv_path:
        csv_paths.append(output_csv_path)

    value_assert(len(csv_paths) > 0,
        'all tables are empty, cannot create empty GameSet')

    return _create_zip_from_files(csv_paths, output_filename)


def calculate_gameset_hash(gameset_path: str) -> str:
    """Calculate the SHA256 hash of a GameSet ZIP file for UI
        verification. Returns: hex string of hash.
    """
    type_assert(isinstance(gameset_path, str), 'gameset_path must be str')
    value_assert(isfile(gameset_path),
        f'gameset_path must be valid file: {gameset_path}')

    hash_obj = sha256()
    with open(gameset_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def get_column_types(model_class: type[SqlModel]) -> dict[str, str]:
    """Get column type mappings from model class annotations. Returns
        dict mapping column name to type str, with fallback to 'str' for
        columns lacking annotations.
    """
    column_types: dict[str, str] = {}

    if hasattr(model_class, '__annotations__'):
        for column_name, annotation in model_class.__annotations__.items():
            if column_name in model_class.columns:
                origin = get_origin(annotation)

                if origin is None:
                    column_type = annotation
                elif origin is type(None).__class__ or origin in (list, set):
                    args = get_args(annotation)
                    if args:
                        column_type = args[0]
                    else:
                        column_type = str
                else:
                    args = get_args(annotation)
                    if args and args[0] is not type(None):
                        column_type = args[0]
                    else:
                        column_type = annotation

                if column_type is Default:
                    args = get_args(annotation)
                    if args and args[0] is not type(None):
                        column_type = args[0]
                    else:
                        column_type = str

                if type(column_type) is not str:
                    column_types[column_name] = str(column_type)
                else:
                    column_types[column_name] = column_type

    for column_name in model_class.columns:
        if column_name not in column_types:
            column_types[column_name] = 'str'

    return column_types


def _parse_csv_value(value: str, column_type: type|str) -> any:
    """Parse a CSV string value to the proper Python type for database
        insertion. Returns: parsed value.
    """
    if value == '~None~':
        return None

    if column_type in (bytes, bytes | None) or (
            type(column_type) is str and column_type[:5] == 'bytes'
        ):
        return bytes.fromhex(value)
    elif column_type in (int, int | None, int | Default) or (
            type(column_type) is str and column_type[:3] == 'int'
        ):
        return int(value)
    else:
        return value


def _backup_database(db_filepath: str, backup_path: str | None = None) -> str | None:
    """Backup existing database file. If backup_path is None, generates
        'backup.{timestamp}.{db_filepath}'. Returns: path to backup file
        or None if database doesn't exist.
    """
    type_assert(isinstance(db_filepath, str), 'db_filepath must be str')
    type_assert(backup_path is None or isinstance(backup_path, str),
        'backup_path must be None or str')

    if not isfile(db_filepath):
        return None

    if backup_path is None:
        timestamp = str(int(time()))
        filename = path.basename(db_filepath)
        backup_path = f"backup.{timestamp}.{filename}"
        backup_dir = path.dirname(db_filepath)
        if backup_dir:
            backup_path = path.join(backup_dir, backup_path)

    copy2(db_filepath, backup_path)
    return backup_path


def _extract_csvs_from_zip(zip_path: str, extract_dir: str) -> list[str]:
    """Extract CSV files from a ZIP archive to the specified directory.
        Returns: list of extracted CSV file paths.
    """
    type_assert(isinstance(zip_path, str), 'zip_path must be str')
    type_assert(isinstance(extract_dir, str), 'extract_dir must be str')
    value_assert(isfile(zip_path), f'zip_path must be valid file: {zip_path}')

    makedirs(extract_dir, exist_ok=True)
    extracted_paths: list[str] = []

    with ZipFile(zip_path, 'r') as zip_file:
        for member in zip_file.namelist():
            if member.endswith('.csv'):
                zip_file.extract(member, extract_dir)
                extracted_paths.append(path.join(extract_dir, member))

    return extracted_paths


def _import_csv_to_model(
        csv_path: str,
        model_class: type[SqlModel],
        chunk_size: int = 500
    ) -> None:
    """Import CSV data to a database table using batch insertion.
        Only imports columns that exist in both the CSV and the model.
        Handles None values, hex-encoded bytes, and integer conversions.
    """
    type_assert(isinstance(csv_path, str), 'csv_path must be str')
    type_assert(isinstance(model_class, type), 'model_class must be type')
    type_assert(isinstance(chunk_size, int) and chunk_size > 0,
        'chunk_size must be positive int')

    column_types = get_column_types(model_class)

    with open(csv_path, 'r', encoding='utf-8') as f:
        csv_reader = reader(f)
        header = next(csv_reader)

        valid_columns = [
            col for col in header if col in model_class.columns
        ]

        if not valid_columns:
            return

        records: list[dict] = []
        for row in csv_reader:
            row_dict: dict = {}

            for col_name, value in zip(header, row):
                if col_name in valid_columns:
                    row_dict[col_name] = _parse_csv_value(
                        value, column_types[col_name]
                    )

            records.append(row_dict)

            if len(records) >= chunk_size:
                model_class.insert_many(records)
                records = []

        if records:
            model_class.insert_many(records)


def apply_gameset(
        gameset_path: str,
        db_filepath: str,
        migrations_path: str,
        backup_path: str | None = None,
    ) -> None:
    """Apply a GameSet ZIP file to restore a database. Backs up the
        existing database if present, creates a fresh database via
        migrations, then imports CSV data from the GameSet.

        The workflow: validate → backup → delete old DB → migrate →
        extract → import CSVs → cleanup. Empty CSVs are skipped.
        Only columns present in both CSV and model are imported.

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

    if isfile(db_filepath):
        remove(db_filepath)

    publish_migrations(migrations_path)
    automigrate(migrations_path, db_filepath)

    temp_dir = mkdtemp()
    try:
        csv_paths = _extract_csvs_from_zip(gameset_path, temp_dir)

        csv_mapping = {
            'txns.csv': Txn,
            'coins.csv': Coin,
            'inputs.csv': Input,
            'outputs.csv': Output,
        }

        for csv_path in csv_paths:
            csv_filename = path.basename(csv_path)
            if csv_filename in csv_mapping:
                model_class = csv_mapping[csv_filename]
                _import_csv_to_model(csv_path, model_class)
    finally:
        for file_name in listdir(temp_dir):
            file_path = path.join(temp_dir, file_name)
            if isfile(file_path):
                remove(file_path)
        rmdir(temp_dir)

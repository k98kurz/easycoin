from .errors import type_assert, value_assert
from enum import Enum
from hashlib import sha256
from sqloquent import SqlModel
from tapescript import Script
import packify


class StampType(Enum):
    SINGLE = 'single'
    SERIES = 'series'
    UNKNOWN = 'unknown'


class StampTemplate(SqlModel):
    connection_info: str = ''
    table: str = 'stamp_templates'
    id_column: str = 'id'
    columns: tuple[str] = (
        'id', 'name', 'description', 'type', 'scripts', 'details', 'version',
        'author', 'tags'
    )
    id: str
    name: str
    description: str|None
    type: str|None
    scripts: bytes|None
    details: bytes|None
    version: str|None
    author: str|None
    tags: str|None

    @property
    def type(self) -> StampType:
        """Records the `StampType` of the template. Defaults to unknown.
            Setting with anything other than a valid `StampType` or
            equivalent str will result in a `TypeError` or `ValueError`.
        """
        return StampType(self.data.get('type', None) or 'unknown')
    @type.setter
    def type(self, val: StampType|str):
        type_assert(type(val) in (StampType, str),
            'type must be StampType or one of ["single", "series", "unknown"]')
        if type(val) is StampType:
            self.data['type'] = val.value
            return
        self.data['type'] = StampType(val).value

    @property
    def scripts(self) -> dict:
        """A dict of Stamp scripts ('L', '_', and '$'). Setting raises
            `TypeError` or `ValueError` for invalid value, and
            `ValueError` with serialized `SyntaxError` or `IndexError`
            message for tapescript compilation errors (bad source code).
        """
        if self.data.get('scripts', None) is None:
            return {}
        return packify.unpack(self.data['scripts'])
    @scripts.setter
    def scripts(self, val: dict):
        type_assert(type(val) is dict, 'scripts must be dict')
        value_assert(all([k in ('L', '_', '$') for k in val]),
            'scripts can only be "L" (mint lock), "_" (prefix), or "$" (covenant)')
        type_assert(all([type(v) is str for v in val.values()]),
            'scripts must be str source code')
        for k,v in val.items():
            try:
                Script.from_src(v)
            except BaseException as e:
                raise ValueError(
                    f"Compilation error for {k}: {type(e).__name__}: {e}"
                )
        self.data['scripts'] = packify.pack(val)

    @property
    def details(self) -> dict|None:
        """A dict of Stamp details at the 'd' key; i.e. this data will
            be pre-filled into that part of the stamped Coin if this
            StampTemplate is used. This is important for Stamp Series,
            e.g. fungible tokens with a human-readable name.
        """
        if self.data.get('details', None) is None:
            return None
        return packify.unpack(self.data['details'])
    @details.setter
    def details(self, val: dict|None):
        type_assert(type(val) in (dict, type(None)), 'details must be dict|None')
        self.data['details'] = packify.pack(val)

    @property
    def dsh(self) -> bytes:
        """Derives the dsh (data-script-hash) used for comparing Stamps
            to see if they are within a series.
        """
        scripts = {
            k: Script.from_src(v).bytes
            for k,v in self.scripts.items()
        }
        d = { 'd': self.details, **scripts }
        return sha256(packify.pack(d)).digest()

    @property
    def issue(self) -> bytes:
        """Returns the sha256 of the 'L' mint lock script if one exists."""
        L = Script.from_src(self.scripts.get('L', None) or '')
        return sha256(L.bytes).digest()


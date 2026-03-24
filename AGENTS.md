# Instructions for Agents

## Environment

The environment has been set up in venv/.
Use `source venv/bin/activate` before running any python commands that require the
local environment.

## Git

Do NOT stage changes unless explicitly instructed to.

## Documentation

Before assuming something about the system, check the available documentation in the
docs/ folder:

- models.md: sqloquent models, many of which have important functionality, e.g.
    - Wallet
    - Coin
    - Txn
    - Input
    - Output
    - TrustNet
    - Attestation
    - Confirmation
    - Snapshot
    - Chunk
- sqloquent.md: sqloquent package

Be sure to grep through the files to find the right line numbers before reading them
as they are very long.

## Code Style

### Error Handling

- Do NOT catch, log, or suppress errors regarding UI element querying or updating
    - ALL such errors should crash the app with a stack trace naturally
    - Catching and suppressing errors made from assumptions about the UI structure
    is actively detrimental to the development of this project, so stop doing it
- Catch ONLY errors that are known to occur due to invalid user inputs, e.g. bad
passwords that fail to unlock a wallet and raise a ValueError, or potential database
inconsistencies

### Line length

- Soft max of 80 for normal lines
- Hard max of 85 for code and 72 for docstrings

### Annotations

- This project uses Python 3.10+ style annotations.
- Do NOT use `Union`: use `type1 | type2`
- Do NOT use `Optional`: use `sometype | None`
- Use built-in generic types: `list[type]`, `dict[key, value]`, `set[type]`,
`tuple[type, ...]` instead of `List[type]`, `Dict[key, value]`, etc. (no import
needed)

### Multi-line function/method signatures

- If a function/method signature is long enough to be more than 80 chars, break it
into a multi-line signature
- Parameters should be on their own line, two indentations in
- More than one parameter can be specified per line
- Parameters following a `*` (keyword only) must start on new line
- Final closing parenthesis and return annotation should be on own line one
indentation in (level with function/method body)

Example:
```python
def some_function_with_lots_of_params(
        param1: bytes, param2: str, ..., *,
        kwarg_only_1: bool = False, ...
    ) -> dict[str, int]:
    ...
```

### Multi-line compound conditionals

- Surround with parentheses, with opening parenthesis one indentation layer in
- First conditional should be on same line as opening parenthesis, indented in once
from the opening parenthesis
- Each additional condition should be on its own line, indented in twice, with the
condition combining word at the beginning of the condition

Example:
```python
if  (   some_long_condition_goes >= here_first
        and some_other_condition <= goes_here
    ):
    ...
```

### Docstrings

- Start docstring on same line as openinig quotation marks
- Do not add an empty line before the first and subsequent lines
- Use additional lines in docstring for word wrapping
- Indent additional lines in one level
- Quote code (variable names, types, etc) within the docstring using backticks
- Closing quotation marks on own line except for short, one-line docstrings
- File-level multiline docstrings should be unindented and should start on own line
- Do NOT write docstrings that are improperly indented
- Do NOT add empty lines in docstrings
- Do NOT add "Arg: " and "Returns: " lists
- ONLY include information that is not obvious from the annotations

Examples:
```python
"""
This file does things. It has several functions that do things. Blah
blah blah this is a docstring.
"""

def some_function(x: int, y: int) -> float:
    """This does something. Returns `x / y`."""
    ...

def some_other_function(x: int, y: int, z: int) -> list[float]:
    """This does something else. Returns a list of floats, e.g.
        `x / y`, `z / y`, etc.
    """
    ...
```

### Imports

- Imports must always be at the top of the file, never in function/method bodies
- Group all `from package import whatever` before all `import package` statements
- Then group imports: stdlib first, then external dependencies, then easycoin internal modules
- Order imports alphabetically within each group
- No blank lines between import statements
- Imports come after file-level docstrings

Example:
```python
"""
This is a file-level docstring example. Below, the inline comments are
to explain the import pattern to agents; agents should not replicate
the inline comments in actual code.
"""

from hashlib import sha256 # stdlib
from sys import argv # stdlib
from sqloquent import SqlModel # external package
from sqloquent.tools import automigrate # external package
from easycoin.models import Coin # internal module
import json # stdlib
import os # stdlib
import packify # external package
```

### Textual CUI

#### Event Management

- Prefer using the `BINDINGS` with `action_*()` handlers over `on_key()` 
- Prefer the `@on` decorator over long `on_button_pressed()` methods

#### Element Querying

- If the element has an ID, do NOT specify the element type
    - E.g. do NOT use `self.query_one("#some_id_maps_to_one_element", SomeType)`
    - E.g. DO use `self.query_one("#some_id_maps_to_one_element")`
    - The app will crash if more than one element shares the same ID; specifying
    the element type is redundant and makes refactoring code more difficult for
    no benefit

#### DataTable

- Use "row" cursor type: `table.cursor_type = "row"` after `add_columns()`
- Default cursor highlights individual cells, "row" highlights the whole row
- `table.get_row_at(table.cursor_row)` returns the tuple of column values for
the selected row

#### Element Styling

- Many styles are contained in easycoin/cui/styles.tcss
- Prefer the existing tailwind-like classes over creating a new custom class/whatever
- If there is an opportunity to make a new tailwind-like class for a style, make it
- If custom CSS is required, write it to the `CSS` property of the screen/widget

#### Modals

- Modals should subclass ModalScreen, not Screen
- Content should be contained within a Vertical or VerticalScroll with
`classes="modal-container"`
- Modals should have a Footer at the bottom, outside of the container

### Testing Style

- This project uses unittest from the stdlib, NOT pytest
- Use `assert` with descriptive error messages instead of `self.assertEqual` etc.
- For database tests: use `setUpClass`/`tearDownClass` for migrations, `setUp` to clean all model data
- Define module-level constants: `DB_FILEPATH`, `MIGRATIONS_PATH`, test data (`SEED_PHRASE`, `PASSWORD`, etc.)
- Prefer real objects over mocking; only mock external dependencies
- Use `# setup`, `# p2pk`, etc. inline comments for complex test logic
- Include "e2e" suffix in test names for end-to-end workflow tests
- Import from `context.py` first for shared test setup
```

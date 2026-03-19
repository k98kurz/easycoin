# Instructions for Agents

## Environment

The environment has been set up in venv/.
Use `source venv/bin/activate` before running any python commands that require the
local environment.

## Documentation

Before assuming something about the system, check the available documentation in the
docs/ folder:

- models.md: sqloquent models, many of which have important functionality
- sqloquent.md: sqloquent package

Be sure to grep through the files to find the right line numbers before reading them
as they are very long.

## Code Style

### Line length

- Soft max of 80 for normal lines
- Hard max of 85 for code and 72 for docstrings

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

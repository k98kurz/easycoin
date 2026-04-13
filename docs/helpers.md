# easycoin.helpers

## Functions

### `type_assert(condition: bool, message: str = 'invalid type'):`

Raises TypeError with the given message if the condition is False.

### `value_assert(condition: bool, message: str = 'invalid value'):`

Raises ValueError with the given message if the condition is False.

### `hexify():`

### `format_balance(balance: int, exact: bool = False) -> str:`

Format balance with EC⁻¹ suffix. Uses K/M/B suffixes by default, or exact
formatting with commas if exact=True.

### `format_amount(amount: int, exact: bool = False) -> str:`

Format amount with K/M/B suffix for large values.

### `format_timestamp(ts: int) -> str:`

Format Unix timestamp to readable string.

### `format_timestamp_relative(ts: int) -> str:`

Format timestamp as relative time or full date if older than 24 hours.

### `format_script_src(src: str) -> str:`

Formats tapescript source code to remove weird indentation.

### `truncate_text(text: str, prefix_len: int = 16, suffix_len: int = 8) -> str:`

Truncate text to readable format with ellipsis.

### `estimate_fee_for_witness(lock_type: str, extra_script_len: int = 0) -> int:`

Estimate the required fee for a witness type. Assumes unchanged `WITFEE_MULT`
and `WITFEE_EXP` from the `Txn` model file.

### `sigflags_hex_to_ints(hex_sigflags: str) -> set[int]:`

Extract masked sigfield indices from hex sigflags. Raises `TypeError` or
`ValueError` for invalid input.

### `sigflags_ints_to_hex(sigfield_indices: set) -> str:`

Convert masked sigfield indices to hex sigflags. Raises `TypeError` or
`ValueError` for invalid input.

### `get_image_type(data: bytes) -> str | None:`

Detect image type from magic bytes. Returns 'png', 'jpeg', 'gif', 'webp', or
None if magic bytes are not detected.

### `create_temp_file(content: bytes, filename: str) -> str:`

Create temp file with content, track for cleanup. Returns the file path.

### `open_file_with_default_app(filepath: str):`

Open file with system's default application. Works cross-platform.



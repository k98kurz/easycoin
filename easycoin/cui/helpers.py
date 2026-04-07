from datetime import datetime
from easycoin.models.errors import type_assert, value_assert


def format_balance(balance: int, exact: bool = False) -> str:
    """Format balance with EC⁻¹ suffix. Uses K/M/B suffixes by default,
    or exact formatting with commas if exact=True.
    """
    if exact:
        return f"{balance:,} EC⁻¹"
    else:
        return f"{format_amount(balance)} EC⁻¹"


def format_amount(amount: int) -> str:
    """Format amount with K/M/B suffix for large values."""
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"{amount / 1_000:.2f}K"
    else:
        return f"{amount}"


def format_timestamp(ts: int) -> str:
    """Format Unix timestamp to readable string."""
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_timestamp_relative(ts: int) -> str:
    """Format timestamp as relative time or full date if older than 24 hours."""
    now = datetime.now().timestamp()
    diff = now - ts

    if diff < 60:
        return f"{int(diff)}s ago"
    elif diff < 3600:
        return f"{int(diff // 60)}m ago"
    elif diff < 86400:
        return f"{int(diff // 3600)}h ago"
    else:
        return format_timestamp(ts)


def format_script_src(src: str) -> str:
    """Formats tapescript source code to remove weird indentation."""
    # parse into lines and strip indentation
    lines = src.split('\n')
    lines = [l.strip() for l in lines]

    # remove leading and trailing empty lines
    while len(lines) and len(lines[0]) == 0:
        lines = lines[1:]
    while len(lines) and len(lines[-1]) == 0:
        lines = lines[:-1]

    # re-indent in code blocks
    code = []
    indent_level = 0
    empty_line = False
    for i, l in enumerate(lines):
        # preserve one empty internal line between blocks
        if not l:
            if not empty_line:
                empty_line = True
                code.append('')
            continue
        empty_line = False

        # check for deindentation
        if(   l[:6].lower() == 'end_if'
                or l[:7].lower() == 'end_def'
                or l[:4].lower() == 'else'
                or l[:6].lower() == 'except'
                or l[:10].lower() == 'end_except'
                or l[:8].lower() == 'end_loop'
                or l[:1] == '}'
            ):
            indent_level -= 1

        # add line
        code.append(('    ' * indent_level) + l)

        # check for subsequent indentation/re-indentation
        if  (   'op_if' in (l[:5].lower(), l[-5:].lower())
                or 'if' in (l[:2].lower(), l[-2:].lower())
                or 'else' in (l[:4].lower(), l[-4:].lower())
                or '} else' == l[:6].lower()
                or 'op_def' in (l[:6].lower(), l[-6:].lower())
                or 'def' in (l[:3].lower(), l[-3:].lower())
                or 'op_try' in (l[:6].lower(), l[-6:].lower())
                or 'try' in (l[:3].lower(), l[-3:].lower())
                or 'except' in (l[:6].lower(), l[-6:].lower())
                or 'op_loop' in (l[:7].lower(), l[-7:].lower())
                or 'loop' in (l[:4].lower(), l[-4:].lower())
                or '{' == l[-1:]
            ):
            indent_level += 1

    return '\n'.join(code)


def truncate_text(text: str, prefix_len: int = 16, suffix_len: int = 8) -> str:
    """Truncate text to readable format with ellipsis."""
    value_assert(prefix_len >= 0, 'prefix_len must be >= 0')
    value_assert(suffix_len >= 0, 'suffix_len must be >= 0')
    if len(text) <= prefix_len + suffix_len:
        return text
    if suffix_len > 0:
        return f"{text[:prefix_len]}...{text[-suffix_len:]}"
    else:
        return f"{text[:prefix_len]}..."


def estimate_fee_for_witness(lock_type: str, extra_script_len: int = 0) -> int:
    """Estimate the required fee for a witness type. Assumes unchanged
        `_witfee_mult` and `_witfee_exp` from the `Txn` model file.
    """
    if extra_script_len < 256:
        wlen = extra_script_len
    else:
        wlen = 1 + extra_script_len

    if lock_type in "P2PK":
        wlen = 66
    elif lock_type == "P2PKH":
        wlen = 100
    elif lock_type in "P2TR":
        if not extra_script_len:
            wlen = 66
        else:
            wlen = 2 + extra_script_len + 34
    elif lock_type == "P2SH":
        wlen = 2 + extra_script_len
    elif lock_type == "P2GR":
        if not extra_script_len:
            wlen = 67
        else:
            wlen = 66 + (2 + extra_script_len) + 1
    elif lock_type == "P2GT":
        if not extra_script_len:
            wlen = 66
        else:
            wlen = 64 + (2 + extra_script_len) + (2 + 41) + 34

    return wlen


def sigflags_hex_to_ints(hex_sigflags: str) -> set[int]:
    """Extract masked sigfield indices from hex sigflags. Raises
        `TypeError` or `ValueError` for invalid input.
    """
    type_assert(isinstance(hex_sigflags, str), 'hex_sigflags must be str')
    value_assert(len(hex_sigflags) == 2, 'hex_sigflags must be exactly 2 chars')

    sig_flag = int.from_bytes(bytes.fromhex(hex_sigflags), 'big')
    masked: set[int] = set()
    for i in range(8):
        if sig_flag & (1 << i):
            masked.add(i + 1)
    return masked


def sigflags_ints_to_hex(sigfield_indices: set[int]) -> str:
    """Convert masked sigfield indices to hex sigflags. Raises
        `TypeError` or `ValueError` for invalid input.
    """
    type_assert(isinstance(sigfield_indices, set), 'sigfield_indices must be set')
    value_assert(
        all(isinstance(i, int) and 1 <= i <= 8 for i in sigfield_indices),
        'sigfield_indices must contain only ints in range 1-8'
    )

    sig_flag = 0
    for idx in sigfield_indices:
        sig_flag |= 1 << (idx - 1)
    return sig_flag.to_bytes(1, 'big').hex()


def get_image_type(data: bytes) -> str|None:
    """Detect image type from magic bytes. Returns 'png', 'jpeg', 'gif', 'webp',
        or None if magic bytes are not detected.
    """
    if len(data) < 3:
        return None

    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "png"
    elif data[:3] == b'\xff\xd8\xff':
        return "jpeg"
    elif data[:6] in (b'GIF87a', b'GIF89a'):
        return "gif"
    elif data[:4] == b'RIFF' and len(data) >= 12 and data[8:12] == b'WEBP':
        return "webp"
    else:
        return None


from datetime import datetime
from easycoin.models.errors import value_assert


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


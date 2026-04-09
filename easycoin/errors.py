def type_assert(condition: bool, message: str = 'invalid type'):
    """Raises TypeError with the given message if the condition is False."""
    if not condition:
        raise TypeError(message)

def value_assert(condition: bool, message: str = 'invalid value'):
    """Raises ValueError with the given message if the condition is False."""
    if not condition:
        raise ValueError(message)



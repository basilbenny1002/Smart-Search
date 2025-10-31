"""Shared utility functions"""
import os
import string
import time
from functools import wraps
from config import SYMBOL_MAP, DIGIT_MAP, VALID_SYMBOLS

if os.name == 'nt':
    import ctypes
    FILE_ATTRIBUTE_HIDDEN = 0x02
    FILE_ATTRIBUTE_SYSTEM = 0x04


def timeit(func):
    """Decorator to measure execution time of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__} took {end - start:.4f} seconds")
        return result
    return wrapper


def is_hidden(path: str) -> bool:
    """Return True if path is hidden/system."""
    if os.name == 'nt':
        try:
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs == -1:
                return False
            return bool(attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM))
        except Exception:
            return False
    else:
        return os.path.basename(path).startswith('.')


def is_accessible(path: str) -> bool:
    """Check if we can read (and enter if directory)."""
    if os.path.isdir(path):
        return os.access(path, os.R_OK | os.X_OK)
    return os.access(path, os.R_OK)


def check_letters(s: str) -> bool:
    """Return True if all characters are allowed."""
    ALLOWED = set(string.ascii_letters + string.digits).union(VALID_SYMBOLS)
    return all(ch in ALLOWED for ch in s)


def get_value(ch: str) -> str:
    """Return the valid Tree attribute name for a given character."""
    if ch.isalpha():
        return ch.lower()
    elif ch in DIGIT_MAP:
        return DIGIT_MAP[ch]
    elif ch in SYMBOL_MAP:
        return SYMBOL_MAP[ch]
    else:
        raise ValueError(f"Unsupported character: {ch!r}")


def clean_query(s: str) -> str:
    """Keep only allowed characters."""
    ALLOWED = set(string.ascii_letters + string.digits).union(VALID_SYMBOLS)
    return "".join(ch for ch in (s or "") if ch in ALLOWED).lower()

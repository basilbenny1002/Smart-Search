"""Shared utility functions"""
import os
import string
import time
from functools import wraps
from config import SYMBOL_MAP, DIGIT_MAP, VALID_SYMBOLS, VALID_IMAGE_EXTENSIONS
import json

if os.name == 'nt':
    import ctypes
    FILE_ATTRIBUTE_HIDDEN = 0x02
    FILE_ATTRIBUTE_SYSTEM = 0x04


def timeit(func):
    """Decorator to measure execution time of a function.
        was made to help debug performance issues.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__} took {end - start:.4f} seconds")
        return result
    return wrapper


def is_hidden(path: str) -> bool:
    """Return True if path is hidden/system
    params: path: str - file or directory path
    return: bool - True if hidden/system, False otherwise
    """
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
    """Check if we can read (and enter if directory).
        params: path: str - file or directory path
        return: bool - True if accessible, False otherwise
    """
    if os.path.isdir(path):
        return os.access(path, os.R_OK | os.X_OK)
    return os.access(path, os.R_OK)


def check_letters(s: str) -> bool:
    """Return True if all characters are allowed based on the valid symbols in config and letters and digits.
    param s: str - input string
    return: bool - True if all characters are allowed, False otherwise"""
    ALLOWED = set(string.ascii_letters + string.digits).union(VALID_SYMBOLS)
    return all(ch in ALLOWED for ch in s)


def get_value(ch: str) -> str:
    """Return the valid Tree attribute name for a given character.
    this is used to map characters to tree nodes
    param ch: str - input character 
    return: str - valid attribute name
    """
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


def find_media(directories: list):
    """
    Returns a list of valid image directories
    :param directories:
    :return Valid image directories:
    """
    from config import SKIP_PATTERNS, FILE_DATA_JSON
    
    valid_images = []
    for directories in directories:
        for root, _, files in os.walk(directories):
            if is_hidden(root):
                continue
            
            # Skip paths containing skip patterns
            root_lower = root.lower()
            if any(pattern in root_lower for pattern in SKIP_PATTERNS):
                continue
            
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                if ext in VALID_IMAGE_EXTENSIONS and os.path.getsize(file_path) > 10 * 1024 and 'windows' not in file_path.lower() and 'xampp' not in file_path.lower() and len(file) > 3 and file_path not in valid_images:  # Ignore small files
                    valid_images.append(file_path)
        json_data = {path:"" for path in valid_images}
        with open(FILE_DATA_JSON, 'w') as data:
            json.dump(json_data, data)

    return valid_images
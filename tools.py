import os
from models import FileData, Tree
import string
import sys
import time
from functools import wraps
# from pyuac import main_requires_admin

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


# def is_admin():
#     """Check if the script is running with admin privileges."""
#     try:
#         import ctypes
#         return ctypes.windll.shell32.IsUserAnAdmin() != 0
#     except Exception:
#         return False


# def run_as_admin():
#     """Re-launch the script with admin privileges."""
#     try:
#         import ctypes
#         if not is_admin():
#             # Re-run the program with admin rights
#             ctypes.windll.shell32.ShellExecuteW(
#                 None, "runas", sys.executable, " ".join(sys.argv), None, 1
#             )
#             sys.exit(0)
#     except Exception as e:
#         print(f"Failed to elevate privileges: {e}")
#         print("Continuing without admin privileges...")


# # Uncomment the line below to auto-request admin on script start
# # run_as_admin()

# Windows hidden/system check
if os.name == 'nt':
    import ctypes
    FILE_ATTRIBUTE_HIDDEN = 0x02
    FILE_ATTRIBUTE_SYSTEM = 0x04

    def _is_hidden_windows(path: str) -> bool:
        try:
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs == -1:
                return False
            return bool(attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM))
        except Exception:
            return False


def is_hidden(path: str) -> bool:
    """Return True if path is hidden/system."""
    if os.name == 'nt':
        return _is_hidden_windows(path)
    else:
        return os.path.basename(path).startswith('.')


def is_accessible(path: str) -> bool:
    """Check if we can read (and enter if directory)."""
    if os.path.isdir(path):
        return os.access(path, os.R_OK | os.X_OK)
    return os.access(path, os.R_OK)



def collect_entries(root_dir):
    """
    Collect accessible files and folders (skipping hidden/system and special dirs).
    Returns list of FileData(name, full_path, type).
    """
    # Request admin privileges for better file access
    # run_as_admin()
    
    file_list = []

    # Common system or junk folders to skip
    skip_names = {
        '$recycle.bin',
        'system volume information',
        'config.msi',
        'windows.old',
        '$winreagent',
        '$getcurrent',
        '$sysreset',
        '$av_asw$',
        '$av_asw$',
        'found.000',
    }

    skip_files = {
        'pagefile.sys',
        'hiberfil.sys',
        'swapfile.sys',
    }
    
    # Skip temp/cache folders
    skip_patterns = ['temp', 'tmp', 'cache', '__pycache__', 'node_modules', 'pkg']

    for root, dirs, files in os.walk(root_dir, topdown=True, onerror=lambda e: None):
        allowed_dirs = []
        for d in dirs:
            full_d = os.path.join(root, d)
            name_l = d.lower()

            # skip temp/cache patterns
            if any(pattern in name_l for pattern in skip_patterns):
                continue

            # skip hidden/system/inaccessible/special dirs
            if (
                is_hidden(full_d)
                or name_l in skip_names
                or not is_accessible(full_d)
            ):
                continue

            # include this directory and add it as folder
            allowed_dirs.append(d)
            file_list.append(FileData(d, full_d, 'folder'))

        # modify dirs in-place (so os.walk doesn’t go into skipped dirs)
        dirs[:] = allowed_dirs

        for f in files:
            full_f = os.path.join(root, f)
            name_l = f.lower()

            # skip hidden/system/inaccessible/special files
            if (
                is_hidden(full_f)
                or name_l in skip_files
                or not is_accessible(full_f)
            ):
                continue

            ext = os.path.splitext(f)[1].lower().strip('.') or 'unknown'
            file_list.append(FileData(f, full_f, ext))

    return file_list


SYMBOL_MAP = {
    " ": "space",
    "!": "exclamation",
    "#": "hash",
    "$": "dollar",
    "%": "percent",
    "&": "ampersand",
    "'": "apostrophe",
    ".": "dot",
    "(": "lparen",
    ")": "rparen",
    "-": "dash",
    "@": "at",
    "^": "caret",
    "_": "underscore",
    "`": "backtick",
    "{": "lbrace",
    "}": "rbrace",
    "~": "tilde",
}

DIGIT_MAP = {str(i): f"num{i}" for i in range(10)}

# Combine all names
all_names = (
    list(string.ascii_lowercase) +  # lowercase letters
    list(DIGIT_MAP.values()) +      # numbers (num0–num9)
    list(SYMBOL_MAP.values())       # symbols (space, exclamation, etc.)
)

# Create the tree dictionary
trees = {name: Tree(name) for name in all_names}

def check_letters(s: str) -> bool:
    """Return True if all characters are allowed (letters, digits, or Windows-valid symbols)."""
    SYMBOLS = set(" .!#$%&'()-@^_`{}~")  # added '.' to allowed symbols
    ALLOWED = set(string.ascii_letters + string.digits).union(SYMBOLS)

    for ch in s:
        if ch not in ALLOWED:
            return False
    return True

def get_value(ch: str) -> str:
    """Return the valid Tree attribute name for a given character using global maps."""
    # If it’s a letter (a-z or A-Z), just return it
    if ch.isalpha():
        return ch
    # If it’s a digit
    elif ch in DIGIT_MAP:
        return DIGIT_MAP[ch]
    # If it’s a mapped symbol
    elif ch in SYMBOL_MAP:
        return SYMBOL_MAP[ch]
    else:
        raise ValueError(f"Unsupported character: {ch!r}")
    
@timeit
def generate_tree(root_dir: str):
    for files in collect_entries(root_dir=root_dir):
        if not check_letters(files.file_name):
            continue
        file_name_list = list(files.file_name)
        first_letter = get_value(file_name_list[0].lower())
        root_tree = trees[first_letter]  
        if len(files.file_name) == 1:
            root_tree.files.append(files)
            continue
        # root_tree.files.append(files)
        for i in range(1, len(file_name_list)):
            letter = get_value(file_name_list[i].lower())
            node = getattr(root_tree, letter)
            if node is None:
                new_node = Tree(letter)
                setattr(root_tree, letter, new_node)
                root_tree = new_node
                root_tree.files.append(files)
            elif node is not None and i == len(file_name_list) - 1:
                # new_node = Tree(letter)
                # setattr(root_tree, letter, new_node)
                # root_tree = new_node
                # root_tree.files.append(files)
                node.files.append(files)
            elif node is not None:
                root_tree = node
                root_tree.files.append(files)
                
@timeit
def search_tree(prefix: str):
    """Search for all files matching the prefix."""
    if not prefix:
        return []
    
    # Start at the first letter's tree
    first_letter = get_value(prefix[0].lower())
    current_node = trees.get(first_letter)
    
    if current_node is None:
        return []
    
    # Traverse the tree using get_value for each character
    for ch in prefix[1:]:
        letter = get_value(ch.lower())
        current_node = getattr(current_node, letter, None)
        if current_node is None:
            return []
    
    # Return all files at this node
    return current_node.files if current_node else []

            
# print(is_accessible(r"C:\Users\basil\Downloads\google_maps_data_Roofing_Companies_in_Austin-enriched.csv"))
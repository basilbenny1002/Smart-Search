"""Configuration settings for Fastest Search"""
import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TREES_DIR = os.path.join(DATA_DIR, "trees")
EMBEDDINGS_DB = os.path.join(DATA_DIR, "embeddings.db")
FILE_DATA_JSON = os.path.join(DATA_DIR, "file_data.json")

# UI Settings
UI_DIR = os.path.join(BASE_DIR, "ui")
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 450
WINDOW_HEIGHT_EXPANDED = 650
BACKGROUND_COLOR = "#9494EE"

# Indexing Settings
ROOT_INDEXING_PATH = "C:/"
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}

MIN_IMAGE_SIZE_KB = 10

# Skip patterns for file indexing
SKIP_FOLDERS = {
    '$recycle.bin', 'system volume information', 'config.msi',
    'windows.old', '$winreagent', '$getcurrent', '$sysreset',
    '$av_asw$', 'found.000'
}
SKIP_FILES = {'pagefile.sys', 'hiberfil.sys', 'swapfile.sys'}
SKIP_PATTERNS = ['temp', 'tmp', 'cache', '__pycache__', 'node_modules', 'pkg', ".vscode"]

# Symbols and character mapping
VALID_SYMBOLS = set(" .!#$%&'()-@^_`{}~")
SYMBOL_MAP = {
    " ": "space", "!": "exclamation", "#": "hash", "$": "dollar",
    "%": "percent", "&": "ampersand", "'": "apostrophe", ".": "dot",
    "(": "lparen", ")": "rparen", "-": "dash", "@": "at",
    "^": "caret", "_": "underscore", "`": "backtick",
    "{": "lbrace", "}": "rbrace", "~": "tilde",
}
DIGIT_MAP = {str(i): f"num{i}" for i in range(10)}

# Ensure data directories exist
os.makedirs(TREES_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

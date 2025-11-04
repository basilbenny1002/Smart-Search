"""Configuration settings for Fastest Search"""
import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TREES_DIR = os.path.join(DATA_DIR, "trees")
IMAGE_EMBEDDINGS_DB = os.path.join(DATA_DIR, "image_embeddings.db") #Stoered image embeddings
TEXT_EMBEDDINGS_DB = os.path.join(DATA_DIR, "text_embeddings.db") #Stored text embeddings
FILE_SEARCH_DB = os.path.join(DATA_DIR, "file_search.db") #stored file search database
FILE_DATA_JSON = os.path.join(DATA_DIR, "file_data.json")  #stored file metadata for image embeddings
INDEXED_PATHS_JSON = os.path.join(DATA_DIR, "indexed_paths.json")  #stored paths user chose to index for images/documents

# UI Settings
UI_DIR = os.path.join(BASE_DIR, "ui")
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 450
WINDOW_HEIGHT_EXPANDED = 650 #was 650
BACKGROUND_COLOR = "#9494EE"

# Indexing Settings
ROOT_INDEXING_PATH = "C:/"
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
VALID_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
BATCH_SIZE = 5000  # SQLite batch insert size for file indexing, the higher, the faster but more memory usage

MIN_IMAGE_SIZE_KB = 10 # Minimum image file size to consider (in KB) helps distinguish real images from icons/thumbnails

# Search Settings
DEFAULT_SEARCH_LIMIT = 200  # Default number of search results
MAX_IMAGE_SEARCH_RESULTS = 50  # Maximum results for image search

# Text search model
TEXT_SEARCH_MODEL = "intfloat/e5-base-v2"

# Skip patterns for file indexing
SKIP_FOLDERS = {
    '$recycle.bin', 'system volume information', 'config.msi',
    'windows.old', '$winreagent', '$getcurrent', '$sysreset',
    '$av_asw$', 'found.000'
}
SKIP_FILES = {'pagefile.sys', 'hiberfil.sys', 'swapfile.sys'}
SKIP_PATTERNS = ['temp', 'tmp', 'cache', '__pycache__', 'node_modules', 'pkg', ".vscode"]


# Symbols and character mapping
# Windows allows these symbols in filenames: space ! # $ % & ' ( ) + , - . ; = @ [ ] ^ _ ` { } ~
# Forbidden: \ / : * ? " < > |
VALID_SYMBOLS = set(" .!#$%&'()+,-.;=@[]^_`{}~")
SYMBOL_MAP = {
    " ": "space", "!": "exclamation", "#": "hash", "$": "dollar",
    "%": "percent", "&": "ampersand", "'": "apostrophe", ".": "dot",
    "(": "lparen", ")": "rparen", "+": "plus", ",": "comma",
    "-": "dash", ";": "semicolon", "=": "equals", "@": "at",
    "[": "lbracket", "]": "rbracket", "^": "caret", "_": "underscore",
    "`": "backtick", "{": "lbrace", "}": "rbrace", "~": "tilde",
}
DIGIT_MAP = {str(i): f"num{i}" for i in range(10)}

# Ensure data directories exist
os.makedirs(TREES_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

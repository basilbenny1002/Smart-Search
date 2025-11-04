"""File and folder search functionality"""
import os
import json
import string
from typing import List
from models.data_models import Tree, FileData
from config import DATA_DIR, TREES_DIR, SYMBOL_MAP, DIGIT_MAP
import sqlite3
from utils.helpers import get_value, timeit


# Global trees dictionary
trees = {}

# Initialize trees
all_names = (
    list(string.ascii_lowercase) +
    list(DIGIT_MAP.values()) +
    list(SYMBOL_MAP.values())
)
trees = {name: Tree(name) for name in all_names}


def load_tree(name: str) -> bool:
    """Load a specific tree from disk. Returns True if successful."""
    path = os.path.join(TREES_DIR, f"{name}tree.json")
    if not os.path.isfile(path):
        print(f"Tree file not found: {path}")
        return False
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            loaded_tree = Tree.from_dict(data)
            trees[name] = loaded_tree
            print(f"Loaded tree: {name}")
            return True
    except Exception as e:
        print(f"Error loading tree {name}: {e}")
        return False


def load_trees() -> int:
    """Load trees from JSON files. Returns count loaded."""
    loaded = 0
    for letter in string.ascii_lowercase:
        path = os.path.join(TREES_DIR, f"{letter}tree.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                loaded_tree = Tree.from_dict(data)
                trees[letter] = loaded_tree
                loaded += 1
        except Exception as e:
            print(f"Warning: failed to load {path}: {e}")
    
    # Load digit and symbol trees
    for name in list(DIGIT_MAP.values()) + list(SYMBOL_MAP.values()):
        path = os.path.join(TREES_DIR, f"{name}tree.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                loaded_tree = Tree.from_dict(data)
                trees[name] = loaded_tree
                loaded += 1
        except Exception as e:
            print(f"Warning: failed to load {path}: {e}")
    
    return loaded


def clear_trees() -> None:
    """Clear all tree data from memory to free up RAM."""
    global trees
    for name in trees:
        trees[name] = Tree(name)
    print("Cleared all tree data from memory")


def save_trees() -> None:
    """Save all trees to JSON files."""
    for name, tree in trees.items():
        if tree and hasattr(tree, 'files') and len(tree.files) > 0:
            path = os.path.join(TREES_DIR, f"{name}tree.json")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(tree.to_dict(), f, indent=2)
            except Exception as e:
                print(f"Error saving {path}: {e}")


def build_trees(file_list: List[FileData], progress_callback=None) -> None:
    """Build tree structures from file list."""
    from utils.helpers import check_letters
    
    total = len(file_list)
    for idx, files in enumerate(file_list):
        if not check_letters(files.file_name):
            continue
            
        file_name_list = list(files.file_name)
        first_letter = get_value(file_name_list[0].lower())
        root_tree = trees[first_letter]
        
        if len(files.file_name) == 1:
            root_tree.files.append(files)
            continue
            
        for i in range(1, len(file_name_list)):
            letter = get_value(file_name_list[i].lower())
            node = getattr(root_tree, letter)
            
            if node is None:
                new_node = Tree(letter)
                setattr(root_tree, letter, new_node)
                root_tree = new_node
                root_tree.files.append(files)
            elif node is not None and i == len(file_name_list) - 1:
                node.files.append(files)
            elif node is not None:
                root_tree = node
                root_tree.files.append(files)
        
        if progress_callback and idx % 100 == 0:
            progress_callback(idx, total)


@timeit
def search_tree(prefix: str) -> List[FileData]:
    """Search for all files matching the prefix. Lazy-loads tree if needed."""
    if not prefix:
        return []
    
    first_letter = get_value(prefix[0].lower())
    current_node = trees.get(first_letter)
    
    # If tree is empty (just initialized), try to load it from disk
    if current_node and not current_node.files and not hasattr(current_node, '_loaded'):
        print(f"Lazy-loading tree for: {first_letter}")
        if load_tree(first_letter):
            current_node = trees.get(first_letter)
            # Mark as loaded to avoid reloading
            current_node._loaded = True
    
    if current_node is None:
        return []
    
    for ch in prefix[1:]:
        letter = get_value(ch.lower())
        current_node = getattr(current_node, letter, None)
        if current_node is None:
            return []
    
    return current_node.files if current_node else []

# ========== SQLite-based Search Index (Alternative to Tree) ==========
# This is a new approach that stores file data in SQLite instead of tree structures
# Not yet connected to main code - for review/testing first

def get_file_category(file_type: str) -> str:
    """
    Categorize file by its type/extension.
    Matches the frontend UI categories.
    
    Args:
        file_type: File extension or type (e.g., 'txt', 'pdf', 'folder')
    
    Returns:
        Category string: 'image', 'video', 'audio', 'archive', 'document', 'folder', or 'file'
    """
    t = (file_type or '').lower()
    
    if t == 'folder':
        return 'folder'
    if t in ["png", "jpg", "jpeg", "gif", "bmp", "webp", "image"]:
        return 'image'
    if t in ["mp4", "mkv", "mov", "avi", "video"]:
        return 'video'
    if t in ["mp3", "wav", "flac", "m4a", "audio"]:
        return 'audio'
    if t in ["zip", "7z", "rar", "tar", "gz"]:
        return 'archive'
    if t in ["pdf", "ppt", "pptx", "xls", "xlsx", "csv", "md", "txt", "rtf", "doc", "docx"]:
        return 'document'
    
    return 'file'  # Default category


def initiate_db():
    """Initialize the SQLite database for file search index."""
    from config import DATA_DIR
    db_path = os.path.join(DATA_DIR, "file_search.db")
    conn = sqlite3.connect(db_path)
    
    # Enable WAL mode for faster writes
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    
    cursor = conn.cursor()
    
    # Create table with normalized filename as primary key
    # Added file_extension and file_category for efficient filtering
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            prefix TEXT PRIMARY KEY,
            file_extension TEXT NOT NULL,
            file_category TEXT NOT NULL,
            files_json TEXT NOT NULL
        )
    """)
    
    # Create index for faster LIKE queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_prefix ON file_index(prefix)
    """)
    
    # Create index for category filtering
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_category ON file_index(file_category, prefix)
    """)
    
    # Create index for extension filtering (for future use)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_extension ON file_index(file_extension, prefix)
    """)
    
    conn.commit()
    conn.close()
    print(f"Initialized database at {db_path}")


def build_search_index(file_list: List[FileData], progress_callback=None, batch_size=5000) -> None:
    """
    Build SQLite search index from file list.
    
    Stores each unique filename once with array of FileData objects.
    Uses SQLite's json_insert to append on conflict.
    
    Args:
        file_list: List of FileData objects to index
        progress_callback: Optional callback for progress updates
        batch_size: Number of files to insert per batch (default 5000)
    
    Example:
    - 'test.txt' at C:/Documents → stored once
    - 'test.txt' at C:/Downloads → appended to same key
    """
    initiate_db()
    
    from config import DATA_DIR
    db_path = os.path.join(DATA_DIR, "file_search.db")
    conn = sqlite3.connect(db_path)
    
    # Enable JSON functions
    conn.execute("PRAGMA journal_mode=WAL")
    
    cursor = conn.cursor()
    
    total = len(file_list)
    batch = []
    
    for idx, file_data in enumerate(file_list):
        if not file_data.file_name:
            continue
        
        # Normalize the filename to lowercase
        normalized_name = file_data.file_name.lower()
        
        # Convert special characters using get_value
        prefix_chars = []
        for char in normalized_name:
            prefix_chars.append(get_value(char))
        normalized_key = ''.join(prefix_chars)
        
        # Get file extension and category
        file_extension = file_data.file_type.lower() if file_data.file_type else 'unknown'
        file_category = get_file_category(file_extension)
        
        # Add to batch (key, extension, category, file_json, file_json for conflict)
        file_json = json.dumps([file_data.to_dict()])
        batch.append((normalized_key, file_extension, file_category, file_json, file_json))
        
        # Execute batch when size reached
        if len(batch) >= batch_size:
            # Use INSERT with ON CONFLICT to append
            cursor.executemany("""
                INSERT INTO file_index (prefix, file_extension, file_category, files_json) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(prefix) DO UPDATE SET
                    files_json = json_insert(files_json, '$[#]', json(?))
            """, batch)
            conn.commit()
            batch = []
        
        # Free up memory
        file_list[idx] = None
        
        # Progress callback
        if progress_callback and idx % 100 == 0:
            progress_callback(idx, total)
    
    # Insert remaining batch
    if batch:
        cursor.executemany("""
            INSERT INTO file_index (prefix, file_extension, file_category, files_json) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(prefix) DO UPDATE SET
                files_json = json_insert(files_json, '$[#]', json(?))
        """, batch)
        conn.commit()
    
    conn.close()
    print(f"Search index built with {total} files (unique filenames stored once)")


def search_db(query: str, limit: int = 200, categories: List[str] = None) -> List[FileData]:
    """
    Search the SQLite database for files matching the query prefix.
    Uses LIKE query to find all filenames starting with the prefix.
    
    Args:
        query: Search prefix (e.g., 't', 'te', 'test')
        limit: Maximum number of results to return (default 200)
        categories: Optional list of categories to filter by 
                   (e.g., ['image', 'video'], ['document'], ['folder'])
                   Categories: 'image', 'video', 'audio', 'archive', 'document', 'folder', 'file'
    
    Returns:
        List of FileData objects matching the prefix and categories
    
    Example:
    - search_db('te') → All files starting with 'te'
    - search_db('te', categories=['image']) → Only images starting with 'te'
    - search_db('do', categories=['document', 'folder']) → Documents and folders starting with 'do'
    """
    if not query:
        return []
    
    # Normalize query and convert special characters
    normalized_query = query.lower()
    prefix_chars = []
    for char in normalized_query:
        prefix_chars.append(get_value(char))
    prefix = ''.join(prefix_chars)
    
    from config import DATA_DIR
    db_path = os.path.join(DATA_DIR, "file_search.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Build query with optional category filtering
    if categories:
        # Create placeholders for IN clause
        placeholders = ','.join('?' * len(categories))
        query_sql = f"""
            SELECT files_json FROM file_index
            WHERE prefix LIKE ? AND file_category IN ({placeholders})
            LIMIT ?
        """
        params = [prefix + '%'] + categories + [limit]
    else:
        query_sql = """
            SELECT files_json FROM file_index
            WHERE prefix LIKE ?
            LIMIT ?
        """
        params = [prefix + '%', limit]
    
    cursor.execute(query_sql, params)
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        return []
    
    # Deserialize all matching files
    files = []
    for row in results:
        files_data = json.loads(row[0])
        
        # Handle both single array and nested arrays (due to json_insert behavior)
        if isinstance(files_data, list):
            for item in files_data:
                # If item is a dict (FileData), add it directly
                if isinstance(item, dict):
                    files.append(FileData.from_dict(item))
                # If item is a list (nested due to json_insert), flatten it
                elif isinstance(item, list):
                    for nested_item in item:
                        if isinstance(nested_item, dict):
                            files.append(FileData.from_dict(nested_item))
            
                # Stop if we've reached the limit
                if len(files) >= limit:
                    return files
    
    return files


def search_db_startswith(query: str) -> List[FileData]:
    """
    Search the SQLite database for ALL files that start with the query.
    Uses LIKE query to find all matching prefixes.
    
    Args:
        query: Search prefix (e.g., 'ab', 'test', etc.)
    
    Returns:
        List of FileData objects where filename starts with query
    
    Alternative approach that searches multiple prefix entries.
    """
    if not query:
        return []
    
    # Normalize query
    normalized_query = query.lower()
    prefix_chars = []
    for char in normalized_query:
        prefix_chars.append(get_value(char))
    prefix = ''.join(prefix_chars)
    
    db_path = os.path.join(TREES_DIR, "file_search.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query for all prefixes starting with the query
    # This will return multiple rows
    cursor.execute("""
        SELECT files_json FROM file_index
        WHERE prefix LIKE ?
    """, (prefix + '%',))
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        return []
    
    # Collect all unique files from all matching prefixes
    # Use a dict to avoid duplicates (keyed by file_path)
    unique_files = {}
    for row in results:
        files_json = row[0]
        files_dicts = json.loads(files_json)
        for f_dict in files_dicts:
            file_obj = FileData.from_dict(f_dict)
            # Use file_path as unique key
            unique_files[file_obj.file_path] = file_obj
    
    return list(unique_files.values())


    
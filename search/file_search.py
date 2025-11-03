"""File and folder search functionality"""
import os
import json
import string
from typing import List
from models.data_models import Tree, FileData
from config import TREES_DIR, SYMBOL_MAP, DIGIT_MAP
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

def init_db():
    """Initialize the SQLite database for file search index."""
    db_path = os.path.join(TREES_DIR, "file_search.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table with prefix as primary key and JSON-serialized FileData list
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            prefix TEXT PRIMARY KEY,
            files_json TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"Initialized database at {db_path}")


def build_search_index(file_list: List[FileData], progress_callback=None) -> None:
    """
    Build SQLite search index from file list.
    
    For each file, creates entries for all prefixes:
    - File 'abc.txt' creates entries: 'a', 'ab', 'abc'
    - Each entry stores list of FileData objects as JSON
    
    This version writes directly to DB to save RAM.
    """
    init_db()
    
    db_path = os.path.join(TREES_DIR, "file_search.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    total = len(file_list)
    for idx, file_data in enumerate(file_list):
        if not file_data.file_name:
            continue
        
        # Normalize the filename to lowercase for prefix matching
        normalized_name = file_data.file_name.lower()
        
        # Create all prefixes for this file
        # e.g., "abc" -> ["a", "ab", "abc"]
        for i in range(1, len(normalized_name) + 1):
            # Build prefix character by character
            prefix_chars = []
            for j in range(i):
                char = normalized_name[j]
                # Use get_value to handle special characters
                prefix_chars.append(get_value(char))
            
            prefix = ''.join(prefix_chars)
            
            # Check if prefix already exists
            cursor.execute("""
                SELECT files_json FROM file_index WHERE prefix = ?
            """, (prefix,))
            
            result = cursor.fetchone()
            
            if result:
                # Prefix exists - load existing files, append new one, update
                existing_json = result[0]
                existing_files = json.loads(existing_json)
                existing_files.append(file_data.to_dict())
                
                # Update the row
                cursor.execute("""
                    UPDATE file_index SET files_json = ? WHERE prefix = ?
                """, (json.dumps(existing_files), prefix))
            else:
                # Prefix doesn't exist - create new entry
                files_json = json.dumps([file_data.to_dict()])
                cursor.execute("""
                    INSERT INTO file_index (prefix, files_json) VALUES (?, ?)
                """, (prefix, files_json))
        
        # Free up memory: clear this file's data after it's been written to DB
        # This helps reduce RAM usage during indexing
        file_list[idx] = None
        
        # Commit every 100 files for performance
        if idx % 100 == 0:
            conn.commit()
            if progress_callback:
                progress_callback(idx, total)
    
    # Final commit
    conn.commit()
    conn.close()
    print(f"Search index built with {total} files")


def search_db(query: str) -> List[FileData]:
    """
    Search the SQLite database for files matching the query prefix.
    
    Args:
        query: Search prefix (e.g., 'ab', 'test', etc.)
    
    Returns:
        List of FileData objects matching the prefix
    
    This is an alternative to search_tree() - not yet connected to main code.
    """
    if not query:
        return []
    
    # Normalize query and convert special characters
    normalized_query = query.lower()
    prefix_chars = []
    for char in normalized_query:
        prefix_chars.append(get_value(char))
    prefix = ''.join(prefix_chars)
    
    db_path = os.path.join(TREES_DIR, "file_search.db")
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query for exact prefix match
    cursor.execute("""
        SELECT files_json FROM file_index
        WHERE prefix = ?
    """, (prefix,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result is None:
        return []
    
    # Deserialize JSON back to FileData objects
    files_json = result[0]
    files_dicts = json.loads(files_json)
    files = [FileData.from_dict(f) for f in files_dicts]
    
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


    
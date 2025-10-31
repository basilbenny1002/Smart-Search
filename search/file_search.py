"""File and folder search functionality"""
import os
import json
import string
from typing import List
from models.data_models import Tree, FileData
from config import TREES_DIR, SYMBOL_MAP, DIGIT_MAP
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

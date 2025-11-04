"""File and folder indexing functionality"""
import os
import string
from typing import List
from models.data_models import FileData
from utils.helpers import is_hidden, is_accessible, timeit
from config import SKIP_FOLDERS, SKIP_FILES, SKIP_PATTERNS, ROOT_INDEXING_PATH, VALID_SYMBOLS
from pyuac import main_requires_admin


def has_valid_characters(filename: str) -> bool:
    """Check if filename contains only valid characters (letters, digits, and valid symbols)"""
    ALLOWED = set(string.ascii_letters + string.digits).union(VALID_SYMBOLS)
    return all(ch in ALLOWED for ch in filename)


def collect_entries(root_dir: str) -> List[FileData]:
    """
    Collect accessible files and folders (skipping hidden/system and special dirs).
    Returns list of FileData(name, full_path, type).
    """
    file_list = []
    skipped_count = 0

    for root, dirs, files in os.walk(root_dir, topdown=True, onerror=lambda e: None):
        allowed_dirs = []
        for d in dirs:
            full_d = os.path.join(root, d)
            name_l = d.lower()

            if any(pattern in name_l for pattern in SKIP_PATTERNS):
                continue

            if (is_hidden(full_d) or name_l in SKIP_FOLDERS or not is_accessible(full_d)):
                continue
            
            # Skip directories with invalid characters
            if not has_valid_characters(d):
                skipped_count += 1
                continue

            allowed_dirs.append(d)
            file_list.append(FileData(d, full_d, 'folder'))

        dirs[:] = allowed_dirs

        for f in files:
            full_f = os.path.join(root, f)
            name_l = f.lower()

            if (is_hidden(full_f) or name_l in SKIP_FILES or not is_accessible(full_f)):
                continue
            
            # Skip files with invalid characters
            if not has_valid_characters(f):
                skipped_count += 1
                continue

            ext = os.path.splitext(f)[1].lower().strip('.') or 'unknown'
            file_list.append(FileData(f, full_f, ext))
    
    if skipped_count > 0:
        print(f"Skipped {skipped_count} items with unsupported characters")

    return file_list




def index_files(root_dir: str = ROOT_INDEXING_PATH, progress_callback=None) -> dict:
    """
    Index all files and folders to an SQlite database..
    Returns dict with status and count.
    
    progress_callback: function(stage, message) to report progress
        stage: 'scanning', 'building', 'saving', 'complete'
        message: descriptive text for the current stage
    """
    # Old tree-based indexing (commented out)
    # from search.file_search import build_trees, save_trees, clear_trees
    
    # New SQLite-based indexing
    from search.file_search import build_search_index
    
    try:
        if progress_callback:
            progress_callback('scanning', 'Scanning files... This may take a while depending on storage size')
        
        print(f"Scanning directory: {root_dir}")
        entries = collect_entries(root_dir)
        total = len(entries)
        
        if progress_callback:
            progress_callback('building', f'Building search index for {total:,} entries...')
        
        print(f"Building search index for {total:,} entries...")
        
        # Old tree-based method (commented out)
        # build_trees(entries, progress_callback)
        # entries.clear()
        # del entries
        # save_trees()
        # clear_trees()
        
        # New SQLite-based method
        build_search_index(entries, progress_callback)
        
        # Entries are already cleared by build_search_index (sets teh values to None during iteration to free up memory)
        print("Clearing file list from memory...")
        entries.clear()
        del entries
        
        if progress_callback:
            progress_callback('complete', f'Indexing complete! Indexed {total:,} files and folders')
        
        print("Indexing complete!")
        return {
            "status": "success",
            "message": f"Indexing complete! Indexed {total:,} files and folders",
            "count": total
        }
    except Exception as e:
        print(f"Error during indexing: {e}")
        if progress_callback:
            progress_callback('error', f'Error: {e}')
        return {
            "status": "error",
            "message": f"Failed to index files: {e}",
            "count": 0
        }

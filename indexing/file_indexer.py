"""File and folder indexing functionality"""
import os
from typing import List
from models.data_models import FileData
from utils.helpers import is_hidden, is_accessible, timeit
from config import SKIP_FOLDERS, SKIP_FILES, SKIP_PATTERNS, ROOT_INDEXING_PATH


def collect_entries(root_dir: str) -> List[FileData]:
    """
    Collect accessible files and folders (skipping hidden/system and special dirs).
    Returns list of FileData(name, full_path, type).
    """
    file_list = []

    for root, dirs, files in os.walk(root_dir, topdown=True, onerror=lambda e: None):
        allowed_dirs = []
        for d in dirs:
            full_d = os.path.join(root, d)
            name_l = d.lower()

            if any(pattern in name_l for pattern in SKIP_PATTERNS):
                continue

            if (is_hidden(full_d) or name_l in SKIP_FOLDERS or not is_accessible(full_d)):
                continue

            allowed_dirs.append(d)
            file_list.append(FileData(d, full_d, 'folder'))

        dirs[:] = allowed_dirs

        for f in files:
            full_f = os.path.join(root, f)
            name_l = f.lower()

            if (is_hidden(full_f) or name_l in SKIP_FILES or not is_accessible(full_f)):
                continue

            ext = os.path.splitext(f)[1].lower().strip('.') or 'unknown'
            file_list.append(FileData(f, full_f, ext))

    return file_list


@timeit
def index_files(root_dir: str = ROOT_INDEXING_PATH, progress_callback=None) -> dict:
    """
    Index all files and folders, building tree structures.
    Returns dict with status and count.
    
    progress_callback: function(stage, message) to report progress
        stage: 'scanning', 'building', 'saving', 'complete'
        message: descriptive text for the current stage
    """
    from search.file_search import build_trees, save_trees, clear_trees
    
    try:
        if progress_callback:
            progress_callback('scanning', 'Scanning files... This may take a while depending on storage size')
        
        print(f"Scanning directory: {root_dir}")
        entries = collect_entries(root_dir)
        total = len(entries)
        
        if progress_callback:
            progress_callback('building', f'Generating trees for {total:,} entries...')
        
        print(f"Building search trees for {total:,} entries...")
        build_trees(entries, progress_callback)
        
        # Clear the file list to free memory
        print("Clearing file list from memory...")
        entries.clear()
        del entries
        
        if progress_callback:
            progress_callback('saving', 'Saving trees to disk...')
        
        print("Saving trees to disk...")
        save_trees()
        
        # Clear trees from memory after saving
        print("Clearing trees from memory...")
        clear_trees()
        
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

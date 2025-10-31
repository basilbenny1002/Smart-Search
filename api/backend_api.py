"""Backend API for the search application"""
import os
from typing import List, Dict, Any
import webview

from models.data_models import FileData
from search.file_search import search_tree, load_trees, trees
from indexing.file_indexer import index_files as do_file_indexing
from indexing.image_indexer import index_images as do_image_indexing
from indexing.text_indexer import index_documents as do_text_indexing
from search.image_search import search_images
from search.text_search import search_text_content
from utils.helpers import clean_query, get_value
from config import UI_DIR


def _file_to_dict(fd: FileData) -> Dict[str, Any]:
    """Convert FileData to JSON-serializable dict."""
    return {
        "name": getattr(fd, "file_name", ""),
        "path": getattr(fd, "file_path", ""),
        "type": getattr(fd, "file_type", "unknown"),
        "length": getattr(fd, "length", 0),
    }


class SearchAPI:
    """Main API class for search operations"""
    
    def __init__(self):
        self._base = os.getcwd()
        self._main_window = None
        self._settings_window = None
        self._info_window = None
        self._visible = True
        self._auto_index_enabled = False

    def bind_window(self, window) -> None:
        """Bind the main window reference"""
        self._main_window = window

    # Search methods
    def search(self, query: str, search_type: str = 'normal') -> List[Dict[str, Any]]:
        """Main search entry point"""
        print(f"Search API: query='{query}', type='{search_type}'")
        
        if search_type == 'normal':
            return self._file_search(query)
        elif search_type == 'image':
            return self._image_search(query)
        elif search_type == 'text':
            return self._text_search(query)
        else:
            return self._file_search(query)

    def _file_search(self, query: str) -> List[Dict[str, Any]]:
        """Normal file/folder search"""
        q = clean_query(query)
        if not q:
            return []
        
        # Lazy loading is now handled inside search_tree()
        try:
            matches = search_tree(q)
            print(f"Found {len(matches)} matches")
            return [_file_to_dict(m) for m in (matches or [])]
        except Exception as e:
            print(f"File search error: {e}")
            return []

    def _image_search(self, query: str) -> List[Dict[str, Any]]:
        """Image search by description"""
        try:
            results = search_images(query)
            return [{"name": os.path.basename(p), "path": p, "type": "image"} 
                    for p in results[:50]]
        except Exception as e:
            print(f"Image search error: {e}")
            return []

    def _text_search(self, query: str) -> List[Dict[str, Any]]:
        """Text content search"""
        try:
            return search_text_content(query)
        except Exception as e:
            print(f"Text search error: {e}")
            return []

    # Indexing methods
    def index_files(self) -> Dict[str, Any]:
        """Index all files and folders"""
        return do_file_indexing()

    def index_documents(self) -> Dict[str, Any]:
        """Index document contents"""
        return do_text_indexing()

    def index_images(self) -> Dict[str, Any]:
        """Index image descriptions"""
        return do_image_indexing()

    # Window management
    def open_file(self, path: str, file_type: str = None) -> str:
        """Open a file using default application"""
        try:
            if os.path.exists(path):
                os.startfile(path)
                return "ok"
            return "not-found"
        except Exception as e:
            return f"error: {e}"

    def toggle_window(self) -> str:
        """Toggle main window visibility"""
        try:
            if not self._main_window:
                return "no-window"
            if self._visible:
                self._main_window.hide()
                self._visible = False
            else:
                self._main_window.show()
                self._visible = True
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def open_settings(self) -> str:
        """Open settings window"""
        try:
            if self._settings_window is None:
                self._settings_window = webview.create_window(
                    "Settings", os.path.join(UI_DIR, "settings.html"),
                    width=700, height=600,
                    frameless=True, on_top=True,
                    background_color="#9494EE"
                )
                # Expose methods
                self._settings_window.expose(self.index_files)
                self._settings_window.expose(self.index_documents)
                self._settings_window.expose(self.index_images)
                self._settings_window.expose(self.set_auto_index)
                self._settings_window.expose(self.get_auto_index_state)
                self._settings_window.expose(self.back_to_search)
            else:
                self._settings_window.show()
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def open_info(self) -> str:
        """Open info window"""
        try:
            if self._info_window is None:
                self._info_window = webview.create_window(
                    "Information", os.path.join(UI_DIR, "info.html"),
                    width=700, height=600,
                    frameless=True, on_top=True,
                    background_color="#9494EE"
                )
                self._info_window.expose(self.back_to_search)
            else:
                self._info_window.show()
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def back_to_search(self) -> str:
        """Return to main search window"""
        try:
            if self._settings_window:
                self._settings_window.hide()
            if self._info_window:
                self._info_window.hide()
            if self._main_window:
                self._main_window.show()
                self._visible = True
            return "ok"
        except Exception as e:
            return f"error: {e}"

    # Auto-index settings
    def set_auto_index(self, enabled: bool) -> Dict[str, Any]:
        """Enable/disable auto-indexing"""
        self._auto_index_enabled = enabled
        # TODO: Implement autostart script
        return {
            "status": "success",
            "message": f"Auto-indexing {'enabled' if enabled else 'disabled'}",
            "enabled": enabled
        }

    def get_auto_index_state(self) -> Dict[str, Any]:
        """Get auto-index state"""
        return {"enabled": self._auto_index_enabled}

from __future__ import annotations

import json
import os
import string
import threading
import webview  # pip install pywebview
from typing import List, Dict, Any

# Import project search utilities without modifying them
try:
    from models import Tree, FileData
    from tools import trees, search_tree
except Exception as e:
    raise RuntimeError(f"Failed to import project modules: {e}")


def _clean_query(s: str) -> str:
    """Keep letters, digits, and valid symbols (same as check_letters in tools.py)"""
    VALID_SYMBOLS = set(" .!#$%&'()-@^_`{}~")  # added '.'
    ALLOWED = set(string.ascii_letters + string.digits).union(VALID_SYMBOLS)
    return "".join(ch for ch in (s or "") if ch in ALLOWED).lower()


def load_trees_from_json(base_dir: str = ".") -> int:
    """Load atree.json..ztree.json into tools.trees.
    Returns count of successfully loaded letters.
    """
    loaded = 0
    for letter in string.ascii_lowercase:
        path = os.path.join(base_dir, rf"trees/{letter}tree.json")
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
    return loaded


def _file_to_dict(fd: FileData) -> Dict[str, Any]:
    # Map to a simple JSON-serializable dict used by index.html
    return {
        "name": getattr(fd, "file_name", None) or getattr(fd, "name", ""),
        "path": getattr(fd, "file_path", None) or getattr(fd, "path", ""),
        "type": getattr(fd, "file_type", None) or getattr(fd, "type", "unknown"),
        "length": getattr(fd, "length", len(getattr(fd, "file_name", ""))),
    }


class API:
    def __init__(self) -> None:
        # Lazy-load per letter on first use instead of preloading all 26
        self._base = os.getcwd()
        self._loaded: set[str] = set()
        self._window = None  # set in main
        self._visible = True
        self._settings_window = None
        self._info_window = None
        self._auto_index_enabled = False

    def _ensure_letter_loaded(self, ch: str) -> None:
        """Lazy-load the first-character tree for letters, digits, and mapped symbols.
        Uses the same naming as main.py writes (e.g., 'atree.json', 'num1tree.json', 'dottree.json').
        """
        if not ch:
            return
        key = None  # key used in 'trees' dict
        filename = None  # filename to load

        c0 = ch[0]
        if c0.isalpha():
            key = c0.lower()
            filename = f"{key}tree.json"
        elif c0.isdigit():
            key = f"num{c0}"
            filename = f"{key}tree.json"
        else:
            # Import symbol map lazily to avoid circulars
            try:
                from tools import SYMBOL_MAP as _SYM
            except Exception:
                _SYM = {}
            if c0 in _SYM:
                key = _SYM[c0]
                filename = f"{key}tree.json"
            else:
                return  # unsupported leading char

        if key in self._loaded:
            return
        path = os.path.join(self._base, "trees", filename)
        print(f"Loading tree for {key} from {path}")
        if not os.path.isfile(path):
            print(f"Tree file not found: {path}")
            self._loaded.add(key)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                loaded_tree = Tree.from_dict(data)
                trees[key] = loaded_tree
                print(f"Loaded tree for {key} with {len(loaded_tree.files) if hasattr(loaded_tree, 'files') else 'unknown'} files")
        except Exception as e:
            print(f"Warning: failed to load {path}: {e}")
        finally:
            self._loaded.add(key)

    def _normal_search(self, query: str) -> List[Dict[str, Any]]:
        q = _clean_query(query)
        print(f"Normal search for query='{query}' -> cleaned='{q}'")
        if not q:
            print("No valid characters in query, returning empty")
            return []
        # Lazy load only the first letter's tree if needed
        self._ensure_letter_loaded(q[0])
        try:
            matches = search_tree(q)
            print(f"search_tree returned {len(matches)} matches")
        except Exception as e:
            print(f"search_tree failed for '{q}': {e}")
            matches = []
        result = [_file_to_dict(m) for m in (matches or [])]
        print(f"Returning {len(result)} results")
        return result

    def image_search(self, query: str) -> List[Dict[str, Any]]:
        # Placeholder for image search by description
        # TODO: Implement image search functionality
        # For now, return empty list
        return []

    def text_search(self, query: str) -> List[Dict[str, Any]]:
        # Placeholder for text search
        # TODO: Implement text search functionality
        # For now, return empty list
        return []

    def search(self, query: str, search_type: str = 'normal') -> List[Dict[str, Any]]:  # exposed
        print(f"Search API called with query='{query}', type='{search_type}'")
        if search_type == 'normal':
            return self._normal_search(query)
        elif search_type == 'image':
            return self.image_search(query)
        elif search_type == 'text':
            return self.text_search(query)
        else:
            return self._normal_search(query)

    def bind_window(self, window) -> None:
        self._window = window

    def resize_window(self, height: int) -> str:  # exposed
        """Resize the frameless window height dynamically from JS.
        Keeps width unchanged; clamps to a reasonable range.
        """
        try:
            if not self._window:
                return "no-window"
            clamped = max(70, min(int(height), 700))
            # Read current size to keep width
            try:
                # pywebview >=4 provides width/height on window
                width = getattr(self._window, 'width', None)
                if not width:
                    width = 800
            except Exception:
                width = 800
            self._window.resize(int(width), clamped)
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def show_window(self) -> str:  # exposed
        try:
            if not self._window:
                return "no-window"
            self._window.show()
            self._visible = True
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def hide_window(self) -> str:  # exposed
        try:
            if not self._window:
                return "no-window"
            self._window.hide()
            self._visible = False
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def toggle_window(self) -> str:  # exposed
        try:
            if not self._window:
                return "no-window"
            if self._visible:
                self._window.hide()
                self._visible = False
            else:
                self._window.show()
                self._visible = True
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def open_file(self, path: str, file_type: str | None = None) -> str:  # exposed
        try:
            if os.path.exists(path):
                os.startfile(path)  # Windows-only
                return "ok"
            return "not-found"
        except Exception as e:
            return f"error: {e}"

    def open_settings(self) -> str:  # exposed
        """Open the settings window"""
        try:
            if self._settings_window is None:
                self._settings_window = webview.create_window(
                    "Settings",
                    "settings.html",
                    width=700,
                    height=600,
                    frameless=True,
                    on_top=True,
                    transparent=False,
                    background_color="#9494EE"
                )
                # Expose API methods to settings window
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

    def open_info(self) -> str:  # exposed
        """Open the info window"""
        try:
            if self._info_window is None:
                self._info_window = webview.create_window(
                    "Information",
                    "info.html",
                    width=700,
                    height=600,
                    frameless=True,
                    on_top=True,
                    transparent=False,
                    background_color="#9494EE"
                )
                # Expose API method to info window
                self._info_window.expose(self.back_to_search)
            else:
                self._info_window.show()
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def back_to_search(self) -> str:  # exposed
        """Close settings/info and return to search window"""
        try:
            if self._settings_window:
                self._settings_window.hide()
            if self._info_window:
                self._info_window.hide()
            if self._window:
                self._window.show()
                self._visible = True
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def index_files(self) -> Dict[str, Any]:  # exposed
        """
        Placeholder function to index all files and folders.
        TODO: Implement actual file indexing logic
        """
        try:
            # Simulate indexing process
            import time
            time.sleep(1)  # Simulate work being done
            
            # Return success message
            return {
                "status": "success",
                "message": "Successfully indexed 1,234 files and folders",
                "count": 1234
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to index files: {e}",
                "count": 0
            }

    def index_documents(self) -> Dict[str, Any]:  # exposed
        """
        Placeholder function to index document contents for text search.
        TODO: Implement actual document content indexing logic
        """
        try:
            # Simulate indexing process
            import time
            time.sleep(1.5)  # Simulate work being done
            
            # Return success message
            return {
                "status": "success",
                "message": "Successfully indexed 456 documents",
                "count": 456
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to index documents: {e}",
                "count": 0
            }

    def index_images(self) -> Dict[str, Any]:  # exposed
        """
        Placeholder function to generate image descriptions for search.
        TODO: Implement actual image description generation logic
        """
        try:
            # Simulate indexing process
            import time
            time.sleep(2)  # Simulate work being done
            
            # Return success message
            return {
                "status": "success",
                "message": "Successfully indexed 789 images",
                "count": 789
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to index images: {e}",
                "count": 0
            }

    def set_auto_index(self, enabled: bool) -> Dict[str, Any]:  # exposed
        """
        Placeholder function to enable/disable auto-indexing.
        TODO: Implement actual autostart script logic
        """
        try:
            self._auto_index_enabled = enabled
            
            if enabled:
                # TODO: Add script to Windows autostart
                # Example: Create a shortcut in the Startup folder
                message = "Auto-indexing enabled. Script added to autostart."
            else:
                # TODO: Remove script from Windows autostart
                message = "Auto-indexing disabled. Script removed from autostart."
            
            return {
                "status": "success",
                "message": message,
                "enabled": enabled
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to toggle auto-index: {e}",
                "enabled": self._auto_index_enabled
            }

    def get_auto_index_state(self) -> Dict[str, Any]:  # exposed
        """Get the current auto-index state"""
        return {
            "enabled": self._auto_index_enabled
        }


def main() -> None:
    api = API()

    window = webview.create_window(
        "Search Bar",
        "index.html",
        width=800,
        height=350,  
        frameless=True,
        on_top=True,
        transparent=False,  # Disable transparency to avoid white box
        background_color="#9494EE"  # Dark background (VS Code-like)
        # Or try: '#F3F3F3' for light theme
    )

    # Expose API methods
    window.expose(api.search)
    window.expose(api.open_file)
    window.expose(api.resize_window)
    window.expose(api.toggle_window)
    window.expose(api.show_window)
    window.expose(api.hide_window)
    window.expose(api.open_settings)
    window.expose(api.open_info)
    api.bind_window(window)

    # Optional global hotkey (Ctrl+Space) to toggle window visibility
    def _hotkey_thread():
        try:
            import keyboard  # type: ignore
        except Exception:
            print("Global hotkey not active (install 'keyboard' to enable).")
            return
        try:
            keyboard.add_hotkey('ctrl+space', lambda: api.toggle_window())
            print("Global hotkey active: Ctrl+Space (toggle search)")
            keyboard.wait()  # keep the hook thread alive
        except Exception as e:
            print(f"Failed to register global hotkey: {e}")

    t = threading.Thread(target=_hotkey_thread, daemon=True)
    t.start()
    webview.start(debug=False)


if __name__ == "__main__":
    main()

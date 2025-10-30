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


def _letters_only(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isalpha()).lower()


def load_trees_from_json(base_dir: str = ".") -> int:
    """Load atree.json..ztree.json into tools.trees.
    Returns count of successfully loaded letters.
    """
    loaded = 0
    for letter in string.ascii_lowercase:
        path = os.path.join(base_dir, f"{letter}tree.json")
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

    def _ensure_letter_loaded(self, ch: str) -> None:
        if not ch or not ch.isalpha():
            return
        letter = ch.lower()[0]
        if letter in self._loaded:
            return
        path = os.path.join(self._base, f"{letter}tree.json")
        if not os.path.isfile(path):
            # Nothing to load; leave absent => search will return []
            self._loaded.add(letter)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                loaded_tree = Tree.from_dict(data)
                trees[letter] = loaded_tree
        except Exception as e:
            print(f"Warning: failed to load {path}: {e}")
        finally:
            self._loaded.add(letter)

    def search(self, query: str) -> List[Dict[str, Any]]:  # exposed
        q = _letters_only(query)
        if not q:
            return []
        # Lazy load only the first letter's tree if needed
        self._ensure_letter_loaded(q[0])
        try:
            matches = search_tree(q)
        except Exception as e:
            print(f"search_tree failed for '{q}': {e}")
            matches = []
        return [_file_to_dict(m) for m in (matches or [])]

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


def main() -> None:
    api = API()

    window = webview.create_window(
        "Search Bar",
        "index.html",
        width=800,
        height=90,
        frameless=True,
        on_top=True,
        # pywebview expects a hex triplet, no alpha channel. Keep the page UI translucent instead.
        background_color="#000000",
    )

    # Expose API methods
    window.expose(api.search)
    window.expose(api.open_file)
    window.expose(api.resize_window)
    window.expose(api.toggle_window)
    window.expose(api.show_window)
    window.expose(api.hide_window)
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

    # Start UI
    webview.start()


if __name__ == "__main__":
    main()

import os
import json
import string
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# Import project search utilities without modifying them
try:
    from models import Tree, FileData
    from tools import trees, search_tree
except Exception as e:
    raise RuntimeError(f"Failed to import project modules: {e}")

# ---------------------------
# Data loading (from existing JSON files)
# ---------------------------

def load_trees_from_json(base_dir: str = ".") -> int:
    """
    Load prebuilt letter trees (atree.json .. ztree.json) from the current folder
    into tools.trees in-place. Returns the number of letters successfully loaded.

    This mirrors the logic in main.py but avoids writing or regenerating trees.
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
            # Keep going even if one letter fails
            print(f"Warning: failed to load {path}: {e}")
    return loaded

# ---------------------------
# GUI implementation
# ---------------------------

class SearchOverlay(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fast Search")
        # Keep a slim overlay look
        self.attributes('-topmost', True)
        # On Windows, overrideredirect removes window frame; bind escape to hide
        self.overrideredirect(True)

        # Position near top center of the primary screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = 800
        height = 360
        x = int((screen_w - width) / 2)
        y = int(screen_h * 0.18)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Container frame with padding and a simple border
        container = ttk.Frame(self, padding=(12, 12, 12, 12))
        container.pack(fill=tk.BOTH, expand=True)
        container.configure(borderwidth=1, relief=tk.SOLID)

        # Search bar row
        entry_row = ttk.Frame(container)
        entry_row.pack(fill=tk.X, pady=(0, 8))

        self.query_var = tk.StringVar()
        self.entry = ttk.Entry(entry_row, textvariable=self.query_var, font=("Segoe UI", 12))
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.search_btn = ttk.Button(entry_row, text="Search", command=self.perform_search_now)
        self.search_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Info/status label
        self.status_var = tk.StringVar(value="Type to search (letters only)")
        self.status = ttk.Label(container, textvariable=self.status_var, foreground="#666")
        self.status.pack(anchor=tk.W, pady=(0, 6))

        # Results list
        list_frame = ttk.Frame(container)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.results = tk.Listbox(list_frame, activestyle='dotbox', font=("Consolas", 10))
        self.results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.results.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results.configure(yscrollcommand=scrollbar.set)

        # Key bindings
        self.entry.bind("<Return>", lambda e: self.perform_search_now())
        self.entry.bind("<Escape>", lambda e: self.hide())
        self.bind("<Escape>", lambda e: self.hide())
        self.results.bind("<Return>", self.open_selected)
        self.results.bind("<Double-1>", self.open_selected)
        self.results.bind("<Escape>", lambda e: self.hide())

        # Live search with debounce
        self._debounce_after = None
        self.query_var.trace_add("write", self._on_text_change)

        # Load trees
        loaded = load_trees_from_json()
        if loaded == 0:
            self.status_var.set("No letter trees found (atree.json..ztree.json). Results will be empty.")
        else:
            self.status_var.set(f"Loaded {loaded} letter trees. Type to search…")

        # Start hidden initially; use show() to display
        self.withdraw()

    def show(self):
        self.deiconify()
        self.lift()
        self.attributes('-topmost', True)
        # Give it a frame-like title bar feel by drawing a simple border when visible
        self.after(0, lambda: self.entry.focus_set())

    def hide(self):
        self.withdraw()

    def toggle(self):
        if self.state() == 'withdrawn':
            self.show()
        else:
            self.hide()

    def _on_text_change(self, *args):
        # Debounce the live search
        if self._debounce_after is not None:
            try:
                self.after_cancel(self._debounce_after)
            except Exception:
                pass
        self._debounce_after = self.after(200, self.perform_search_now)

    def _validate_query(self, q: str) -> str:
        q = (q or "").strip()
        # tools.check_letters expects letters only; we align with that
        letters_only = ''.join(ch for ch in q if ch.isalpha())
        return letters_only

    def perform_search_now(self):
        q = self._validate_query(self.query_var.get())
        if not q:
            self._render_results([])
            self.status_var.set("Type to search (letters only)")
            return
        try:
            matches = search_tree(q)
        except Exception as e:
            matches = []
            print(f"search_tree failed for '{q}': {e}")
        self._render_results(matches, query=q)

    def _render_results(self, items, query: str | None = None):
        self.results.delete(0, tk.END)
        count = 0
        for item in items or []:
            try:
                display = f"{item.file_name}  —  {item.file_path}"
            except Exception:
                display = str(item)
            self.results.insert(tk.END, display)
            count += 1
        if query:
            self.status_var.set(f"{count} result(s) for '{query}'")
        else:
            self.status_var.set("")

    def open_selected(self, event=None):
        # Open the file path of the selected result (Windows)
        try:
            sel = self.results.curselection()
            if not sel:
                return
            idx = sel[0]
            text = self.results.get(idx)
            # Extract path after the long dash ' — '
            parts = text.split('  —  ', 1)
            if len(parts) == 2:
                path = parts[1]
                if os.path.exists(path):
                    try:
                        os.startfile(path)  # Windows-only
                    except Exception as e:
                        messagebox.showerror("Open failed", f"Could not open file:\n{e}")
                else:
                    messagebox.showwarning("Not found", f"Path does not exist:\n{path}")
        except Exception as e:
            print(f"open_selected error: {e}")

# ---------------------------
# Optional global hotkey support (Ctrl+Space)
# ---------------------------

def _run_global_hotkey(app: SearchOverlay, hotkey: str = 'ctrl+space'):
    """
    Register a global hotkey using the 'keyboard' package, if present. Falls back silently
    if the package is unavailable.
    """
    try:
        import keyboard  # type: ignore
    except Exception:
        print("Global hotkey not active (install 'keyboard' to enable). Window starts hidden.")
        return

    def on_hotkey():
        try:
            app.toggle()
        except Exception as e:
            print(f"Hotkey toggle failed: {e}")

    # 'keyboard' runs its own hook thread; we set it here
    try:
        keyboard.add_hotkey(hotkey, on_hotkey)
        print(f"Global hotkey active: {hotkey} (press to toggle search)")
    except Exception as e:
        print(f"Failed to register global hotkey: {e}")

# ---------------------------
# Entry point
# ---------------------------

if __name__ == "__main__":
    app = SearchOverlay()

    # Start optional global hotkey listener in a daemon thread to avoid blocking Tk
    t = threading.Thread(target=_run_global_hotkey, args=(app,), daemon=True)
    t.start()

    # Also bind an app-local shortcut to toggle (Ctrl+Shift+F) while the window has focus
    app.bind_all('<Control-Shift-F>', lambda e: app.toggle())

    # Show once on start for discoverability; press Esc to hide
    app.show()
    app.mainloop()

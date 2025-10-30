from __future__ import annotations
import os
import json
import string
import threading
import tkinter as tk
"""
Modern overlay search GUI using PyQt with a glossy translucent rounded rectangle.
Results appear only after explicit search (Enter or clicking the Search button).
No other project files are changed.

If PyQt6 is unavailable, PyQt5 will be attempted. If neither is available, a
message will be printed with install instructions.
"""



import os
import json
import string
import threading
from typing import List

# Import project search utilities without modifying them
try:
    from models import Tree, FileData
    from tools import trees, search_tree
except Exception as e:
    raise RuntimeError(f"Failed to import project modules: {e}")

# Try PyQt6 then PyQt5
QtCore = QtGui = QtWidgets = None  # type: ignore
try:  # PyQt6
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT_VER = 6
except Exception:
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
        PYQT_VER = 5
    except Exception:
        PYQT_VER = 0


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


if PYQT_VER == 0:
    def _print_install_help():
        print(
            "PyQt6 or PyQt5 is required for the modern UI.\n"
            "Install with one of the following commands:\n"
            "  pip install PyQt6\n"
            "  # or\n"
            "  pip install PyQt5\n"
            "Then run: python GUI.py"
        )

else:
    # ---------------------------
    # GUI implementation (PyQt)
    # ---------------------------

    class RoundedPanel(QtWidgets.QWidget):
        """A QWidget that draws a translucent blue gradient with rounded corners."""

        def __init__(self, radius: int = 18, parent=None):
            super().__init__(parent)
            self.radius = radius
            # Enable translucent background for rounded corners
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)

        def paintEvent(self, event):  # noqa: N802 (Qt naming)
            painter = QtGui.QPainter(self)
            painter.setRenderHints(
                QtGui.QPainter.RenderHint.Antialiasing
                | QtGui.QPainter.RenderHint.SmoothPixmapTransform
            )
            rect = self.rect().adjusted(1, 1, -1, -1)

            # Glossy blue gradient with slight transparency (use float coords for PyQt5/6)
            grad = QtGui.QLinearGradient(
                float(rect.left()), float(rect.top()), float(rect.right()), float(rect.bottom())
            )
            grad.setColorAt(0.0, QtGui.QColor(40, 120, 255, 210))
            grad.setColorAt(0.5, QtGui.QColor(60, 150, 255, 190))
            grad.setColorAt(1.0, QtGui.QColor(20, 80, 200, 210))

            path = QtGui.QPainterPath()
            rectf = QtCore.QRectF(rect)
            path.addRoundedRect(rectf, float(self.radius), float(self.radius))
            painter.fillPath(path, QtGui.QBrush(grad))

            # Subtle inner highlight for glossy feel
            pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 60))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawPath(path)

            painter.end()


    class SearchOverlay(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()

            # Frameless, always on top, tool window
            flags = (
                QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.Tool
                | QtCore.Qt.WindowType.WindowStaysOnTopHint
            )
            self.setWindowFlags(flags)
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
            if PYQT_VER == 6:
                self.setWindowTitle("Fast Search")
            else:
                self.setWindowTitle("Fast Search")

            # Main rounded panel
            self.panel = RoundedPanel(radius=18)
            shadow = QtWidgets.QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(24)
            shadow.setXOffset(0)
            shadow.setYOffset(6)
            shadow.setColor(QtGui.QColor(0, 0, 0, 120))
            self.panel.setGraphicsEffect(shadow)

            # Search row
            self.input = QtWidgets.QLineEdit()
            self.input.setPlaceholderText("Search files (letters only)")
            self.input.setClearButtonEnabled(True)
            self.input.setMinimumHeight(36)
            self.input.setStyleSheet(
                "QLineEdit {"
                "  border: 1px solid rgba(255,255,255,80);"
                "  border-radius: 12px;"
                "  padding: 6px 10px;"
                "  background: rgba(255,255,255,140);"
                "  color: #0a1f3f;"
                "  selection-background-color: rgba(20,100,255,160);"
                "}"
            )

            # Search icon inside line edit
            try:
                style = self.style()
                sp = (
                    QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView
                    if PYQT_VER == 6
                    else QtWidgets.QStyle.SP_FileDialogContentsView
                )
                icon = style.standardIcon(sp)
                action = self.input.addAction(icon, QtWidgets.QLineEdit.ActionPosition.LeadingPosition)
            except Exception:
                action = None  # Optional; not critical

            self.search_btn = QtWidgets.QPushButton(" Search")
            self.search_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.search_btn.setIcon(self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_ArrowForward if PYQT_VER == 6 else QtWidgets.QStyle.SP_ArrowForward
            ))
            self.search_btn.setMinimumHeight(36)
            self.search_btn.setStyleSheet(
                "QPushButton {"
                "  border: none;"
                "  border-radius: 12px;"
                "  padding: 6px 14px;"
                "  color: white;"
                "  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                "    stop:0 rgba(0,110,255,220), stop:1 rgba(0,70,200,220));"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                "    stop:0 rgba(20,130,255,230), stop:1 rgba(0,90,220,230));"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0,70,200,230);"
                "}"
            )

            # Status text (small, subtle)
            self.status = QtWidgets.QLabel("Type a query and press Enter or Search")
            self.status.setStyleSheet("color: rgba(255,255,255,190);")

            # Results list (hidden until a search is performed)
            self.results = QtWidgets.QListWidget()
            self.results.setVisible(False)
            self.results.setStyleSheet(
                "QListWidget {"
                "  border: none;"
                "  background: rgba(255,255,255,120);"
                "  color: #0a1f3f;"
                "  border-radius: 10px;"
                "}"
                "QListWidget::item { padding: 8px 10px; }"
                "QListWidget::item:selected { background: rgba(20,100,255,120); }"
            )

            # Layout inside the rounded panel
            panel_layout = QtWidgets.QVBoxLayout(self.panel)
            panel_layout.setContentsMargins(16, 16, 16, 16)
            panel_layout.setSpacing(10)

            row = QtWidgets.QHBoxLayout()
            row.addWidget(self.input, stretch=1)
            row.addWidget(self.search_btn)
            panel_layout.addLayout(row)
            panel_layout.addWidget(self.status)
            panel_layout.addWidget(self.results, stretch=1)

            # Outer layout to provide transparent background around rounded panel
            outer = QtWidgets.QVBoxLayout(self)
            outer.setContentsMargins(4, 4, 4, 4)
            outer.addWidget(self.panel)

            # Signals
            self.input.returnPressed.connect(self.perform_search_now)  # type: ignore[attr-defined]
            self.search_btn.clicked.connect(self.perform_search_now)  # type: ignore[attr-defined]
            self.results.itemActivated.connect(self.open_selected)  # type: ignore[attr-defined]
            self.results.itemDoubleClicked.connect(self.open_selected)  # type: ignore[attr-defined]

            # Live search (debounced)
            self.debounce_timer = QtCore.QTimer(self)
            self.debounce_timer.setSingleShot(True)
            # self.debounce_timer.setInterval(200)
            self.debounce_timer.timeout.connect(self.perform_search_now)  # type: ignore[attr-defined]
            self.input.textChanged.connect(self._on_text_changed)  # type: ignore[attr-defined]

            # List behavior: single select, row select, hover to select
            self.results.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
            self.results.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
            self.results.setMouseTracking(True)
            self.results.viewport().setMouseTracking(True)
            self.results.viewport().installEventFilter(self)

            # Load trees now
            loaded = load_trees_from_json()
            if loaded == 0:
                self.status.setText("No letter trees found (atree.json..ztree.json). Results will be empty.")
            else:
                self.status.setText(f"Loaded {loaded} letter trees. Press Enter or Search to query…")

            # Size and position: long bar near top center
            self.resize(820, 96)
            self._move_to_top_center()

        def _move_to_top_center(self):
            try:
                if PYQT_VER == 6:
                    screen = QtWidgets.QApplication.primaryScreen()
                    geom = screen.availableGeometry()
                else:
                    screen = QtWidgets.QApplication.primaryScreen()
                    geom = screen.availableGeometry()
                x = int((geom.width() - self.width()) / 2)
                y = int(geom.height() * 0.15)
                self.move(geom.left() + x, geom.top() + y)
            except Exception:
                pass

        def keyPressEvent(self, event):  # noqa: N802 (Qt naming)
            # ESC hides window; Up/Down navigate results; Enter opens when list focused
            key = event.key()
            Key = QtCore.Qt.Key
            if (PYQT_VER == 6 and key == Key.Key_Escape) or (PYQT_VER == 5 and key == Key.Key_Escape):
                self.hide()
                event.accept()
                return

            if self.results.isVisible() and self.results.count() > 0:
                if (PYQT_VER == 6 and key in (Key.Key_Down, Key.Key_Up)) or (PYQT_VER == 5 and key in (Key.Key_Down, Key.Key_Up)):
                    if self.input.hasFocus():
                        self.results.setFocus()
                        if key == Key.Key_Down:
                            self.results.setCurrentRow(0)
                        else:
                            self.results.setCurrentRow(self.results.count() - 1)
                        event.accept()
                        return
                if (PYQT_VER == 6 and key == Key.Key_Return) or (PYQT_VER == 5 and key in (Key.Key_Return, Key.Key_Enter)):
                    if self.results.hasFocus() and self.results.currentRow() >= 0:
                        self.open_selected()
                        event.accept()
                        return

            return super().keyPressEvent(event)

        def eventFilter(self, obj, event):  # noqa: N802
            # Hover to select list items
            try:
                if obj is self.results.viewport():
                    et = event.type()
                    if et in (QtCore.QEvent.Type.MouseMove, QtCore.QEvent.Type.HoverMove):
                        idx = self.results.indexAt(event.pos())
                        if idx.isValid():
                            self.results.setCurrentRow(idx.row())
            except Exception:
                pass
            return super().eventFilter(obj, event)

        @staticmethod
        def _letters_only(q: str) -> str:
            q = (q or "").strip()
            letters_only = ''.join(ch for ch in q if ch.isalpha())
            return letters_only

        def perform_search_now(self):
            q = self._letters_only(self.input.text())
            if not q:
                self.results.clear()
                self.results.setVisible(False)
                self.status.setText("Type a query and press Enter or Search")
                self.resize(820, 96)
                self._move_to_top_center()
                return
            try:
                matches = search_tree(q)  # returns list of FileData-like objects
            except Exception as e:
                print(f"search_tree failed for '{q}': {e}")
                matches = []
            self._render_results(matches, q)

        def _on_text_changed(self):
            # Debounce live search as the user types
            try:
                if self.debounce_timer.isActive():
                    self.debounce_timer.stop()
                self.debounce_timer.start()
            except Exception:
                # Fallback: perform immediately if timer not available
                self.perform_search_now()

        def _render_results(self, items: List[FileData], query: str | None = None):
            self.results.clear()
            count = 0
            for item in items or []:
                try:
                    display = f"{item.file_name}  —  {item.file_path}"
                except Exception:
                    display = str(item)
                self.results.addItem(display)
                count += 1

            if count > 0:
                # Expand to show results
                self.results.setVisible(True)
                # Select first result by default for quick keyboard open
                self.results.setCurrentRow(0)
                # Heuristic height: base + item_height * n (clamped)
                per = 32
                extra = min(8, count) * per + 12
                self.resize(820, 96 + extra)
            else:
                self.results.setVisible(False)
                self.resize(820, 96)

            if query:
                self.status.setText(f"{count} result(s) for '{query}' — press Enter again to refresh")
            self._move_to_top_center()

        def open_selected(self, _item=None):
            try:
                sel = self.results.currentItem()
                if not sel:
                    return
                text = sel.text()
                parts = text.split('  —  ', 1)
                if len(parts) == 2:
                    path = parts[1]
                    if os.path.exists(path):
                        try:
                            os.startfile(path)  # Windows-only
                        except Exception as e:
                            QtWidgets.QMessageBox.critical(self, "Open failed", f"Could not open file:\n{e}")
                    else:
                        QtWidgets.QMessageBox.warning(self, "Not found", f"Path does not exist:\n{path}")
            except Exception as e:
                print(f"open_selected error: {e}")


def _run_global_hotkey_qt(app_widget: 'SearchOverlay', hotkey: str = 'ctrl+space'):
    """Optional global hotkey using keyboard module if available (Windows only)."""
    try:
        import keyboard  # type: ignore
    except Exception:
        print("Global hotkey not active (install 'keyboard' to enable). Window starts hidden.")
        return

    def on_hotkey():
        try:
            if app_widget.isVisible():
                app_widget.hide()
            else:
                app_widget.show()
                app_widget.raise_()
        except Exception as e:
            print(f"Hotkey toggle failed: {e}")

    try:
        keyboard.add_hotkey(hotkey, on_hotkey)
        print(f"Global hotkey active: {hotkey} (press to toggle search)")
    except Exception as e:
        print(f"Failed to register global hotkey: {e}")


# ---------------------------
# Entry point
# ---------------------------

if __name__ == "__main__":
    if PYQT_VER == 0:
        _print_install_help()
    else:
        app = QtWidgets.QApplication([])
        w = SearchOverlay()

        # Start optional global hotkey listener in a daemon thread to avoid blocking the UI
        t = threading.Thread(target=_run_global_hotkey_qt, args=(w,), daemon=True)
        t.start()

        # Show the overlay
        w.show()
        app.exec()

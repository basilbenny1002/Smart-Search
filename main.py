"""
Fastest Search - Main entry point
Press Ctrl+Space to toggle the search window
"""
import threading
import webview
from api.backend_api import SearchAPI
from config import WINDOW_WIDTH, WINDOW_HEIGHT, BACKGROUND_COLOR, UI_DIR
import os


def main():
    """Initialize and start the application"""
    api = SearchAPI()

    # Create main window
    window = webview.create_window(
        "Fastest Search",
        os.path.join(UI_DIR, "index.html"),
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        frameless=True,
        on_top=True,
        transparent=False,
        background_color=BACKGROUND_COLOR
    )

    # Expose API methods to frontend
    window.expose(api.search)
    window.expose(api.open_file)
    window.expose(api.open_file_location)
    window.expose(api.resize_window)
    window.expose(api.toggle_window)
    window.expose(api.open_settings)
    window.expose(api.open_info)
    window.expose(api.check_embeddings_loaded)
    window.expose(api.preload_image_embeddings)
    
    api.bind_window(window)

    # Global hotkey handler (Ctrl+Space)
    def hotkey_thread():
        try:
            import keyboard
            keyboard.add_hotkey('ctrl+space', lambda: api.toggle_window())
            print("Global hotkey active: Ctrl+Space")
            keyboard.wait()
        except ImportError:
            print("Install 'keyboard' package for global hotkey support")
            print("  pip install keyboard")
        except Exception as e:
            print(f"Hotkey registration failed: {e}")

    # Start hotkey listener in background
    threading.Thread(target=hotkey_thread, daemon=True).start()

    # Start the application
    print("Starting Fastest Search...")
    print("Press Ctrl+Space to toggle search window")
    webview.start(debug=False)


if __name__ == "__main__":
    main()

"""Backend API for the search application"""
import os
import subprocess
import base64
import json
import shutil
from typing import List, Dict, Any
import webview

from models.data_models import FileData
# Old tree-based search (commented out)
# from search.file_search import search_tree, load_trees, trees
# New SQLite-based search
from search.file_search import search_db, load_trees, trees
from indexing.file_indexer import index_files as do_file_indexing
from indexing.image_indexer import index_images as do_image_indexing
from indexing.text_indexer import index_documents as do_text_indexing
from search.image_search import search_images, is_embeddings_loaded, force_load_embeddings
from search.text_search import search_text_content
from utils.helpers import clean_query, get_value
from config import UI_DIR, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_HEIGHT_EXPANDED, DEFAULT_SEARCH_LIMIT, MAX_IMAGE_SEARCH_RESULTS, INDEXED_PATHS_JSON


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
        # Path to persistent settings file
        self._settings_path = os.path.join(self._base, 'data', 'settings.json')

        # Load persisted settings (auto-index flag)
        self._auto_index_enabled = False
        self._load_settings()

        # If auto-index was enabled previously, attempt to start the watcher executable
        try:
            if self._auto_index_enabled:
                startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
                startup_exe = os.path.join(startup_folder, 'SmartestSearchWatcher.exe')
                scripts_exe = os.path.join(self._base, 'scripts', 'bin', 'Release', 'net6.0', 'win-x64', 'publish', 'SmartestSearchWatcher.exe')
                exe_to_start = None
                if os.path.exists(startup_exe):
                    exe_to_start = startup_exe
                elif os.path.exists(scripts_exe):
                    exe_to_start = scripts_exe

                if exe_to_start:
                    try:
                        subprocess.Popen([exe_to_start], creationflags=subprocess.CREATE_NO_WINDOW)
                        print('Auto-started file watcher on init')
                    except Exception as e:
                        print(f'Failed to start watcher on init: {e}')
        except Exception:
            pass

    def bind_window(self, window) -> None:
        """Bind the main window reference"""
        self._main_window = window

    # Search methods
    def search(self, query: str, search_type: str = 'normal', category: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """Main search entry point"""
        print(f"Search API: query='{query}', type='{search_type}', category='{category}', limit={limit}")
        
        # Use default limit if not specified
        if limit is None:
            limit = DEFAULT_SEARCH_LIMIT
        
        if search_type == 'normal':
            return self._file_search(query, category, limit)
        elif search_type == 'image':
            return self._image_search(query, limit)
        elif search_type == 'text':
            return self._text_search(query, limit)
        else:
            return self._file_search(query, category, limit)

    def _file_search(self, query: str, category: str = None, limit: int = DEFAULT_SEARCH_LIMIT) -> List[Dict[str, Any]]:
        """Normal file/folder search"""
        q = clean_query(query)
        if not q:
            return []
        
        # Old tree-based search (commented out)
        # try:
        #     matches = search_tree(q)
        #     print(f"Found {len(matches)} matches")
        #     return [_file_to_dict(m) for m in (matches or [])]
        # except Exception as e:
        #     print(f"File search error: {e}")
        #     return []
        
        # New SQLite-based search with category filtering
        try:
            categories = [category] if category else None
            matches = search_db(q, limit=limit, categories=categories)
            print(f"Found {len(matches)} matches")
            return [_file_to_dict(m) for m in (matches or [])]
        except Exception as e:
            print(f"File search error: {e}")
            return []

    def _image_search(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> List[Dict[str, Any]]:
        """Image search by description"""
        try:
            results = search_images(query)
            # Apply limit (cap at MAX_IMAGE_SEARCH_RESULTS for images to avoid loading too many)
            max_results = min(limit, MAX_IMAGE_SEARCH_RESULTS) if limit else MAX_IMAGE_SEARCH_RESULTS
            processed_results = []
            
            for p in results[:max_results]:
                try:
                    # Convert image to base64 for pywebview
                    with open(p, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode('utf-8')
                    
                    # Determine image type from extension
                    ext = os.path.splitext(p)[1].lower()
                    mime_type = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.gif': 'image/gif',
                        '.webp': 'image/webp',
                        '.bmp': 'image/bmp'
                    }.get(ext, 'image/png')
                    
                    processed_results.append({
                        "name": os.path.basename(p), 
                        "path": p, 
                        "type": "image",
                        "image_url": f"data:{mime_type};base64,{encoded}"
                    })
                except Exception as e:
                    print(f"Error loading image {p}: {e}")
                    continue
            
            return processed_results
        except Exception as e:
            print(f"Image search error: {e}")
            return []

    def _text_search(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> List[Dict[str, Any]]:
        """Text content search"""
        try:
            # Note: search_text_content would need to be updated to accept limit parameter
            # For now, we'll just pass through and slice results
            results = search_text_content(query)
            return results[:limit] if limit else results
        except Exception as e:
            print(f"Text search error: {e}")
            return []

    # Indexing methods
    def index_files(self) -> Dict[str, Any]:
        """Index all files and folders"""
        return do_file_indexing()

    def index_documents(self, paths: List[str] = None) -> Dict[str, Any]:
        """Index document contents"""
        if not paths:
            # If no paths provided, use default paths
            paths = self.get_default_document_paths()
        
        print(f"Indexing documents from {len(paths)} path(s): {paths}")
        
        # Save paths to indexed_paths.json
        self._save_indexed_paths('document_paths', paths)
        
        return do_text_indexing(paths)

    def index_images(self, paths: List[str] = None) -> Dict[str, Any]:
        """Index images from specified paths"""
        if not paths:
            # If no paths provided, use default paths
            paths = self.get_default_image_paths()
        
        print(f"Indexing images from {len(paths)} path(s): {paths}")
        
        # Save paths to indexed_paths.json
        self._save_indexed_paths('image_paths', paths)
        
        return do_image_indexing(paths)
    
    def _save_indexed_paths(self, key: str, paths: List[str]) -> None:
        """Save indexed paths to JSON file"""
        try:
            # Load existing data
            if os.path.exists(INDEXED_PATHS_JSON):
                with open(INDEXED_PATHS_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {'image_paths': [], 'document_paths': []}
            
            # Update with new paths (merge, avoiding duplicates)
            existing_paths = set(data.get(key, []))
            new_paths = existing_paths.union(set(paths))
            data[key] = list(new_paths)
            
            # Save back
            os.makedirs(os.path.dirname(INDEXED_PATHS_JSON), exist_ok=True)
            with open(INDEXED_PATHS_JSON, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            print(f"Saved {len(data[key])} {key} to indexed_paths.json")
        except Exception as e:
            print(f"Error saving indexed paths: {e}")
    
    # Image search embedding management
    def check_embeddings_loaded(self) -> Dict[str, Any]:
        """Check if image embeddings are currently loaded"""
        return {
            "loaded": is_embeddings_loaded()
        }
    
    def preload_image_embeddings(self) -> Dict[str, Any]:
        """Preload image embeddings into memory"""
        try:
            print("Preloading image embeddings...")
            emb, paths = force_load_embeddings()
            if emb is not None:
                return {
                    "status": "success",
                    "message": f"Loaded {len(paths)} image embeddings",
                    "count": len(paths)
                }
            else:
                return {
                    "status": "warning",
                    "message": "No embeddings found in database",
                    "count": 0
                }
        except Exception as e:
            print(f"Error preloading embeddings: {e}")
            return {
                "status": "error",
                "message": f"Failed to load embeddings: {e}",
                "count": 0
            }
    
    def get_default_image_paths(self) -> List[str]:
        """Get default image paths for the current user"""
        username = os.getenv('USERNAME') or os.getenv('USER') or 'User'
        base_path = os.path.expanduser('~')
        
        paths = [
            os.path.join(base_path, 'Documents'),
            os.path.join(base_path, 'Pictures'),
            os.path.join(base_path, 'Pictures', 'Screenshots'),
            os.path.join(base_path, 'OneDrive', 'Pictures'),
            os.path.join(base_path, 'OneDrive', 'Pictures', 'Screenshots'),
            os.path.join(base_path, 'OneDrive', 'Documents'),
            os.path.join(base_path, 'Desktop')
        ]
        
        # Only return paths that exist
        return [p for p in paths if os.path.exists(p)]
    
    def get_default_document_paths(self) -> List[str]:
        """Get default document paths for the current user"""
        base_path = os.path.expanduser('~')
        
        paths = [
            os.path.join(base_path, 'Documents'),
            os.path.join(base_path, 'Downloads'),
            os.path.join(base_path, 'Downloads', 'Documents'),
            os.path.join(base_path, 'Desktop'),
            os.path.join(base_path, 'OneDrive', 'Documents'),
        ]
        
        # Only return paths that exist
        return [p for p in paths if os.path.exists(p)]
    
    def get_username(self) -> str:
        """Get current username"""
        return os.getenv('USERNAME') or os.getenv('USER') or 'User'
    
    def select_folder(self) -> str:
        """Open folder selection dialog"""
        try:
            if self._settings_window:
                result = self._settings_window.create_file_dialog(
                    webview.FOLDER_DIALOG,
                    directory=os.path.expanduser('~')
                )
                if result and len(result) > 0:
                    return result[0]
            return None
        except Exception as e:
            print(f"Error selecting folder: {e}")
            return None

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
    
    def open_file_location(self, path: str) -> str:
        """Open file location in explorer and highlight the file"""
        try:
            if os.path.exists(path):
                # Use subprocess to open explorer with the file selected
                subprocess.run(["explorer", "/select,", os.path.normpath(path)])
                return "ok"
            return "not-found"
        except Exception as e:
            return f"error: {e}"
    
    def resize_window(self, expand: bool) -> str:
        """Resize main window - expand for results, collapse when empty"""
        try:
            if not self._main_window:
                return "no-window"
            
            # Preserve current width, only change height
            current_width = self._main_window.width
            new_width = current_width if current_width else WINDOW_WIDTH
            new_height = WINDOW_HEIGHT_EXPANDED if expand else WINDOW_HEIGHT
            
            print(f"Resizing window to: {new_width}x{new_height} (expand={expand})")
            
            # Try setting width and height properties directly instead of resize()
            try:
                self._main_window.width = new_width
                self._main_window.height = new_height
            except:
                # Fallback to resize if properties don't work
                self._main_window.resize(new_width, new_height)
            
            return "ok"
        except Exception as e:
            print(f"Error resizing window: {e}")
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
            # Always destroy and recreate to ensure fresh state
            if self._settings_window is not None:
                try:
                    self._settings_window.destroy()
                except:
                    pass
                self._settings_window = None
            
            self._settings_window = webview.create_window(
                "Settings", os.path.join(UI_DIR, "settings.html"),
                width=700, height=700,
                frameless=True, on_top=True,
                background_color="#9494EE"
            )
            # Expose methods
            self._settings_window.expose(self.index_files)
            self._settings_window.expose(self.index_documents)
            self._settings_window.expose(self.index_images)
            self._settings_window.expose(self.get_default_image_paths)
            self._settings_window.expose(self.get_default_document_paths)
            self._settings_window.expose(self.get_username)
            self._settings_window.expose(self.select_folder)
            self._settings_window.expose(self.set_auto_index)
            self._settings_window.expose(self.get_auto_index_state)
            self._settings_window.expose(self.back_to_search_from_settings)
            self._settings_window.expose(self.open_info)  # Allow opening info from settings
            
            return "ok"
        except Exception as e:
            return f"error: {e}"

    def open_info(self) -> str:
        """Open info window"""
        try:
            # Always destroy and recreate to ensure fresh state
            if self._info_window is not None:
                try:
                    self._info_window.destroy()
                except:
                    pass
                self._info_window = None
            
            self._info_window = webview.create_window(
                "Information", os.path.join(UI_DIR, "info.html"),
                width=700, height=600,
                frameless=True, on_top=True,
                background_color="#9494EE"
            )
            self._info_window.expose(self.back_to_search_from_info)
            
            return "ok"
        except Exception as e:
            return f"error: {e}"
    
    def back_to_search_from_settings(self) -> str:
        """Return to main search window from settings"""
        try:
            print("back_to_search_from_settings called")
            if self._settings_window:
                print("Destroying settings window")
                self._settings_window.destroy()
                self._settings_window = None
            if self._main_window:
                print("Showing main window")
                self._main_window.show()
                self._visible = True
            print("back_to_search_from_settings completed")
            return "ok"
        except Exception as e:
            print(f"Error in back_to_search_from_settings: {e}")
            return f"error: {e}"
    
    def back_to_search_from_info(self) -> str:
        """Return to main search window from info"""
        try:
            print("back_to_search_from_info called")
            if self._info_window:
                print("Destroying info window")
                self._info_window.destroy()
                self._info_window = None
            if self._main_window:
                print("Showing main window")
                self._main_window.show()
                self._visible = True
            print("back_to_search_from_info completed")
            return "ok"
        except Exception as e:
            print(f"Error in back_to_search_from_info: {e}")
            return f"error: {e}"

    def back_to_search(self) -> str:
        """Return to main search window"""
        try:
            print("back_to_search called")  # Debug log
            if self._settings_window:
                print("Destroying settings window")
                self._settings_window.destroy()
                self._settings_window = None  # Reset so it gets recreated next time
            if self._info_window:
                print("Destroying info window")
                self._info_window.destroy()
                self._info_window = None
            if self._main_window:
                print("Showing main window")
                self._main_window.show()
                self._visible = True
            print("back_to_search completed successfully")
            return "ok"
        except Exception as e:
            print(f"Error in back_to_search: {e}")
            return f"error: {e}"

    # Auto-index settings
    def set_auto_index(self, enabled: bool) -> Dict[str, Any]:
        """Enable/disable auto-indexing by building and adding/removing watcher from startup"""
        try:
            # Define paths
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            scripts_dir = os.path.join(base_dir, "scripts")
            watcher_exe_name = "SmartestSearchWatcher.exe"
            
            # Startup folder path
            startup_folder = os.path.join(
                os.getenv('APPDATA'),
                r'Microsoft\Windows\Start Menu\Programs\Startup'
            )
            startup_exe_path = os.path.join(startup_folder, watcher_exe_name)
            
            if enabled:
                # Step 1: Check if .exe already exists (from previous build)
                watcher_exe = os.path.join(scripts_dir, "bin", "Release", "net6.0", "win-x64", "publish", watcher_exe_name)
                
                if not os.path.exists(watcher_exe):
                    # Step 2: Build the C# project
                    print("Building file watcher executable...")
                    build_result = self._build_watcher(scripts_dir)
                    
                    if not build_result["success"]:
                        return {
                            "status": "error",
                            "message": f"Failed to build watcher: {build_result.get('error', 'Unknown error')}",
                            "enabled": False
                        }
                    
                    watcher_exe = build_result["exe_path"]
                
                # Step 3: Copy to startup folder
                print(f"Copying watcher to startup folder: {startup_folder}")
                shutil.copy(watcher_exe, startup_exe_path)
                
                # Step 3b: Copy auto_index.py to startup folder (so watcher can find it)
                auto_index_py = os.path.join(base_dir, "auto_index.py")
                startup_auto_index_path = os.path.join(startup_folder, "auto_index.py")
                
                if os.path.exists(auto_index_py):
                    print(f"Copying auto_index.py to startup folder")
                    shutil.copy(auto_index_py, startup_auto_index_path)
                else:
                    print(f"WARNING: auto_index.py not found at {auto_index_py}")
                
                # Step 4: Start the watcher now
                print("Starting file watcher...")
                subprocess.Popen([startup_exe_path], creationflags=subprocess.CREATE_NO_WINDOW)

                # Persist setting
                self._auto_index_enabled = True
                try:
                    self._save_settings()
                except Exception:
                    pass
                return {
                    "status": "success",
                    "message": "Auto-indexing enabled. File watcher is now running.",
                    "enabled": True
                }
            else:
                # Disable: Remove from startup and kill process
                if os.path.exists(startup_exe_path):
                    os.remove(startup_exe_path)
                
                # Also remove auto_index.py from startup folder
                startup_auto_index_path = os.path.join(startup_folder, "auto_index.py")
                if os.path.exists(startup_auto_index_path):
                    os.remove(startup_auto_index_path)
                
                # Kill any running watcher processes
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/IM', watcher_exe_name],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except:
                    pass  # Ignore if process not running
                # Persist setting
                self._auto_index_enabled = False
                try:
                    self._save_settings()
                except Exception:
                    pass
                return {
                    "status": "success",
                    "message": "Auto-indexing disabled. File watcher stopped.",
                    "enabled": False
                }
                
        except Exception as e:
            print(f"Error in set_auto_index: {e}")
            return {
                "status": "error",
                "message": str(e),
                "enabled": False
            }
    
    def _build_watcher(self, scripts_dir: str) -> Dict[str, Any]:
        """Build the C# file watcher executable"""
        try:
            # Check if dotnet is installed
            dotnet_check = subprocess.run(
                ['dotnet', '--version'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if dotnet_check.returncode != 0:
                return {
                    "success": False,
                    "error": ".NET SDK not found. Please install .NET 6.0 SDK or later."
                }
            
            # Run dotnet publish
            print(f"Building with .NET {dotnet_check.stdout.strip()}...")
            build_process = subprocess.run(
                ['dotnet', 'publish', '-c', 'Release', '-r', 'win-x64', 
                 '--self-contained', 'true', '-p:PublishSingleFile=true', '-p:PublishTrimmed=true'],
                cwd=scripts_dir,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if build_process.returncode != 0:
                return {
                    "success": False,
                    "error": f"Build failed: {build_process.stderr}"
                }
            
            # Find the built executable
            exe_path = os.path.join(scripts_dir, "bin", "Release", "net6.0", "win-x64", "publish", "SmartestSearchWatcher.exe")
            
            if not os.path.exists(exe_path):
                return {
                    "success": False,
                    "error": "Build succeeded but executable not found at expected location"
                }
            
            print(f"Build successful: {exe_path}")
            return {
                "success": True,
                "exe_path": exe_path
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_auto_index_state(self) -> Dict[str, Any]:
        """Get auto-index state"""
        return {"enabled": self._auto_index_enabled}

    def _load_settings(self) -> None:
        """Load persistent settings from disk (if present)."""
        try:
            if os.path.exists(self._settings_path):
                with open(self._settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._auto_index_enabled = bool(data.get('auto_index_enabled', False))
            else:
                self._auto_index_enabled = False
        except Exception as e:
            print(f"Error loading settings: {e}")
            self._auto_index_enabled = False

    def _save_settings(self) -> None:
        """Save persistent settings to disk."""
        try:
            os.makedirs(os.path.dirname(self._settings_path), exist_ok=True)
            with open(self._settings_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'auto_index_enabled': bool(self._auto_index_enabled)
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

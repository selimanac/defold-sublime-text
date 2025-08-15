import sublime
import os
import json
import urllib.request
import zipfile
import shutil
import re
import threading
from datetime import datetime

class DefoldAnnotationsManager:
    GITHUB_API_URL = "https://api.github.com/repos/astrochili/defold-annotations/releases/latest"
    DOWNLOAD_FOLDER = os.path.join(sublime.packages_path(), "Defold", "annotations")
    
    @classmethod
    def check_and_update(cls, on_complete=None):
        """Check for updates and download if available"""
        thread = threading.Thread(target=cls._check_and_update_async, args=(on_complete,))
        thread.daemon = True
        thread.start()
    
    @classmethod
    def _check_and_update_async(cls, on_complete):
        try:
            # Create download folder if it doesn't exist
            os.makedirs(cls.DOWNLOAD_FOLDER, exist_ok=True)
            
            # Get current version (if any)
            current_version = cls._get_current_version()
            print(f"Current annotations version: {current_version}")
            
            # Get latest version from GitHub
            latest_info = cls._get_latest_release_info()
            latest_version = latest_info.get("tag_name", "").strip("v")
            download_url = cls._get_zip_url(latest_info)
            
            print(f"Latest annotations version: {latest_version}")
            
            # Compare versions
            if not current_version or cls._version_is_newer(latest_version, current_version):
                print(f"Updating annotations to version {latest_version}")
                
                # Delete old version if it exists
                if os.path.exists(cls.DOWNLOAD_FOLDER):
                    print("Removing old annotations...")
                    for item in os.listdir(cls.DOWNLOAD_FOLDER):
                        item_path = os.path.join(cls.DOWNLOAD_FOLDER, item)
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                
                # Download and extract new version
                cls._download_and_extract(download_url, latest_version)
                cls._update_lsp_settings(latest_version)
                
                message = f"Defold Lua annotations updated to version {latest_version}"
            else:
                message = f"Defold Lua annotations are up to date (version {current_version})"
            
            # Call the completion callback on the main thread
            if on_complete:
                sublime.set_timeout(lambda: on_complete(message, latest_version), 0)
        
        except Exception as e:
            error_message = f"Error updating annotations: {str(e)}"
            print(error_message)
            if on_complete:
                sublime.set_timeout(lambda: on_complete(error_message, None), 0)
    
    @classmethod
    def _get_current_version(cls):
        """Get the currently installed version"""
        version_file = os.path.join(cls.DOWNLOAD_FOLDER, "version.txt")
        if os.path.exists(version_file):
            try:
                with open(version_file, "r") as f:
                    return f.read().strip()
            except:
                pass
        return None
    
    @classmethod
    def _get_latest_release_info(cls):
        """Get information about the latest release from GitHub"""
        req = urllib.request.Request(
            cls.GITHUB_API_URL,
            headers={"User-Agent": "Sublime Text Defold Plugin"}
        )
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    
    @classmethod
    def _get_zip_url(cls, release_info):
        """Extract the download URL for the ZIP file"""
        assets = release_info.get("assets", [])
        for asset in assets:
            if asset["name"].endswith(".zip"):
                return asset["browser_download_url"]
        raise Exception("Could not find ZIP download in the latest release")
    
    @classmethod
    def _version_is_newer(cls, version_a, version_b):
        """Compare version strings (e.g., '1.2.3' > '1.2.0')"""
        def parse_version(v):
            return [int(x) for x in re.findall(r'\d+', v)]
            
        a_parts = parse_version(version_a)
        b_parts = parse_version(version_b)
        
        for i in range(max(len(a_parts), len(b_parts))):
            a = a_parts[i] if i < len(a_parts) else 0
            b = b_parts[i] if i < len(b_parts) else 0
            if a > b:
                return True
            elif a < b:
                return False
        return False
    
    @classmethod
    def _download_and_extract(cls, url, version):
        """Download and extract the ZIP file"""
        zip_path = os.path.join(cls.DOWNLOAD_FOLDER, "annotations.zip")
        
        # Download the file
        print(f"Downloading annotations from {url}...")
        with urllib.request.urlopen(url) as response, open(zip_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        
        # Extract the ZIP file
        print("Extracting annotations...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(cls.DOWNLOAD_FOLDER)
        
        # Remove the ZIP file
        os.remove(zip_path)
        
        # Save the version number
        with open(os.path.join(cls.DOWNLOAD_FOLDER, "version.txt"), "w") as f:
            f.write(version)
        
        print(f"Annotations version {version} installed successfully")
    
    @classmethod
    def _update_lsp_settings(cls, version):
        """Update LSP-Lua settings to use the annotations"""
        try:
            print(f"Contents of download folder: {os.listdir(cls.DOWNLOAD_FOLDER)}")
            
            # Find the annotations directory
            annotation_dir = None
            
            # First, check if the "defold_api" directory exists directly
            defold_api_path = os.path.join(cls.DOWNLOAD_FOLDER, "defold_api")
            if os.path.isdir(defold_api_path):
                annotation_dir = defold_api_path
                print(f"Found defold_api directory: {annotation_dir}")
            else:
                # Fall back to the previous detection logic
                for item in os.listdir(cls.DOWNLOAD_FOLDER):
                    item_path = os.path.join(cls.DOWNLOAD_FOLDER, item)
                    if os.path.isdir(item_path):
                        # Look inside each directory for a lua directory or api files
                        if os.path.exists(os.path.join(item_path, "api")) or os.path.exists(os.path.join(item_path, "library")):
                            annotation_dir = item_path
                            print(f"Found annotations directory: {annotation_dir}")
                            break
                
                # If not found, use the parent directory itself if it contains any files
                if not annotation_dir:
                    lua_files = [f for f in os.listdir(cls.DOWNLOAD_FOLDER) 
                               if f.endswith(".lua") or f.endswith(".json")]
                    if lua_files:
                        annotation_dir = cls.DOWNLOAD_FOLDER
                        print(f"Using download folder as annotations directory")
            
            if not annotation_dir:
                print("Could not find annotations directory. Available items:")
                for item in os.listdir(cls.DOWNLOAD_FOLDER):
                    item_path = os.path.join(cls.DOWNLOAD_FOLDER, item)
                    print(f" - {item} ({'directory' if os.path.isdir(item_path) else 'file'})")
                return
            
            # Update the settings using the appropriate method
            try:
                # First try the LSP API approach (cleaner method)
                cls._update_via_lsp_api(annotation_dir)
            except ImportError as e:
                print(f"LSP API not available ({str(e)}), falling back to settings file")
                # Fall back to updating the settings file directly
                cls._update_via_settings_file(annotation_dir)
            
        except Exception as e:
            print(f"Error updating LSP settings: {str(e)}")
            import traceback
            traceback.print_exc()

    @classmethod
    def _update_via_lsp_api(cls, annotation_dir):
        """Update LSP settings using the LSP API with proper format"""
        try:
            import LSP
            from LSP.plugin import register_plugin
            from LSP.plugin import unregister_plugin
            
            # Use the client settings approach to update both parts
            client_settings = sublime.load_settings("LSP-lua.sublime-settings")
            
            # 1. First update the top-level settings
            top_level_settings = client_settings.get("settings", {})
            if top_level_settings:
                # Update with the new annotation path
                top_level_settings["Lua.workspace.library"] = [annotation_dir]
                
                # Also update other Defold-specific settings
                top_level_settings.update({
                    "Lua.runtime.version": "Lua 5.1",
                    "Lua.diagnostics.globals": [
                        "init", "final", "update", "fixed_update", 
                        "on_message", "on_input", "on_reload"
                    ],
                    "files.associations": {
                        "*.script": "lua",
                        "*.gui_script": "lua",
                        "*.render_script": "lua",
                        "*.editor_script": "lua"
                    }
                })
                
                # Save the updated top-level settings
                client_settings.set("settings", top_level_settings)
            
            # 2. Update configurations if you want to keep both approaches
            # (You can comment this out if you only want the top-level settings)
            configs = client_settings.get("configurations", [])
            configs = [c for c in configs if c.get("name") != "Defold"]
            configs.append({
                "name": "Defold",
                "files": ["game.project", "*%.script", "*%.gui_script"],
                "settings": {
                    "Lua.runtime.version": "Lua 5.1",
                    "Lua.workspace.library": [annotation_dir],
                    "Lua.diagnostics.globals": [
                        "init", "final", "update", "fixed_update", 
                        "on_message", "on_input", "on_reload"
                    ],
                    "files.associations": {
                        "*.script": "lua",
                        "*.gui_script": "lua",
                        "*.render_script": "lua",
                        "*.editor_script": "lua"
                    }
                }
            })
            client_settings.set("configurations", configs)
            
            # Save all changes
            sublime.save_settings("LSP-lua.sublime-settings")
            
            print(f"LSP-Lua settings updated in both top-level settings and configurations")
            print(f"Annotations path: {annotation_dir}")
            print("Please restart Sublime Text to apply the changes.")
                
        except Exception as e:
            print(f"Error in LSP API: {str(e)}")
            import traceback
            traceback.print_exc()
            # Fall back to settings file approach
            cls._update_via_settings_file(annotation_dir)

    @classmethod
    def _update_via_settings_file(cls, annotation_dir):
        """Update only the top-level settings to make Defold settings global"""
        try:
            settings = sublime.load_settings("LSP-lua.sublime-settings")
            
            # Get existing top-level settings
            top_level_settings = settings.get("settings", {})
            
            # Update with Defold-specific settings
            defold_settings = {
                "Lua.runtime.version": "Lua 5.1",
                "Lua.workspace.library": [annotation_dir],
                "Lua.diagnostics.globals": [
                    "init", "final", "update", "fixed_update", 
                    "on_message", "on_input", "on_reload"
                ],
                "files.associations": {
                    "*.script": "lua",
                    "*.gui_script": "lua",
                    "*.render_script": "lua",
                    "*.editor_script": "lua"
                }
            }
            
            # Merge with existing settings (overwrite only Defold-specific ones)
            for key, value in defold_settings.items():
                top_level_settings[key] = value
                
            # Set the updated settings
            settings.set("settings", top_level_settings)
            
            # Remove any Defold configuration from configurations array
            configs = settings.get("configurations", [])
            if configs:
                configs = [c for c in configs if c.get("name") != "Defold"]
                settings.set("configurations", configs)
            
            # Save all changes
            sublime.save_settings("LSP-lua.sublime-settings")
            
            print(f"Global LSP-Lua settings updated with Defold settings")
            print(f"Annotations path: {annotation_dir}")
            
        except Exception as e:
            print(f"Error updating settings file: {str(e)}")
            import traceback
            traceback.print_exc()
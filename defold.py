import sublime
import sublime_plugin
import subprocess
import os
import json
import threading
import time
import urllib.request
import urllib.error

class DefoldSettings:
    @staticmethod
    def get():
        return sublime.load_settings("Defold.sublime-settings")

    @staticmethod
    def save():
        sublime.save_settings("Defold.sublime-settings")

# Global tracking for the extender service
EXTENDER_RUNNING = False

# Port file watcher for monitoring changes
class DefoldPortWatcher(threading.Thread):
    def __init__(self, path, callback):
        threading.Thread.__init__(self)
        self.path = path
        self.callback = callback
        self.last_modified = None
        self.last_exists = os.path.exists(path)
        self.is_running = True
        self.daemon = True
        print("Created port watcher for {}".format(path))

    def run(self):
        while self.is_running:
            try:
                exists = os.path.exists(self.path)
                
                # Check if file was created or deleted
                if exists != self.last_exists:
                    self.last_exists = exists
                    if exists:
                        # File was created
                        with open(self.path, "r") as f:
                            port_content = f.read().strip()
                            if port_content.isdigit():
                                print("Port file created with port {}".format(port_content))
                                self.callback(int(port_content))
                                self.last_modified = os.path.getmtime(self.path)
                    else:
                        # File was deleted
                        print("Port file deleted: {}".format(self.path))
                        self.callback(None)
                        self.last_modified = None
                
                # Check if file was modified
                elif exists and self.last_modified is not None:
                    modified = os.path.getmtime(self.path)
                    if self.last_modified != modified:
                        self.last_modified = modified
                        with open(self.path, "r") as f:
                            port_content = f.read().strip()
                            if port_content.isdigit():
                                print("Port file modified with port {}".format(port_content))
                                self.callback(int(port_content))
            except Exception as e:
                print("Error in port file watcher: {}".format(e))
                
            time.sleep(1)

    def stop(self):
        self.is_running = False

class DefoldManager:
    _instance = None
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = DefoldManager()
        return cls._instance
    
    def __init__(self):
        self.projects = {}  # project_path -> {port: port, watcher: watcher}
        print("DefoldManager initialized")
    
    def is_defold_project(self, project_path):
        """Check if a directory is a Defold project"""
        if not project_path:
            return False
            
        game_project_path = os.path.join(project_path, "game.project")
        result = os.path.exists(game_project_path)
        if result:
            print("Defold project detected: {}".format(project_path))
        return result
    
    def register_project(self, project_path):
        """Register a Defold project to monitor its port file"""
        if not self.is_defold_project(project_path):
            return False
            
        # Already registered
        if project_path in self.projects:
            return True
            
        print("Registering Defold project: {}".format(project_path))
        
        # Get the port file path
        port_file = os.path.join(project_path, ".internal", "editor.port")
        
        # Create the port directory if it doesn't exist
        port_dir = os.path.dirname(port_file)
        if not os.path.exists(port_dir):
            try:
                os.makedirs(port_dir)  # Python 3.3 doesn't have exist_ok parameter
            except Exception as e:
                print("Failed to create port directory: {}".format(e))
        
        # Setup the port callback
        def port_callback(port):
            if project_path in self.projects:
                self.projects[project_path]['port'] = port
                print("Updated port for {} to {}".format(project_path, port))
                
        # Store initial project info
        self.projects[project_path] = {
            'path': project_path,
            'port': None,
            'watcher': None
        }
        
        # Create a port file watcher
        watcher = DefoldPortWatcher(port_file, port_callback)
        self.projects[project_path]['watcher'] = watcher
        
        # Start the watcher
        watcher.start()
        
        # Do an initial check if the port file exists
        if os.path.exists(port_file):
            try:
                with open(port_file, "r") as f:
                    port_content = f.read().strip()
                    if port_content.isdigit():
                        port = int(port_content)
                        self.projects[project_path]['port'] = port
                        print("Initial port for {}: {}".format(project_path, port))
            except Exception as e:
                print("Error reading port file: {}".format(e))
        
        # Check if we should auto-start the extender
        global EXTENDER_RUNNING
        if not EXTENDER_RUNNING:
            settings = DefoldSettings.get()
            if settings.get("auto_start_extender", False):
                print("Auto-starting extender for project: {}".format(project_path))
                self.start_extender_server()
        
        return True
    
    def unregister_project(self, project_path):
        """Unregister a project and stop its port watcher"""
        if project_path in self.projects:
            print("Unregistering project: {}".format(project_path))
            if self.projects[project_path]['watcher']:
                self.projects[project_path]['watcher'].stop()
            del self.projects[project_path]
    
    def get_current_project(self):
        """Get the currently active project path"""
        window = sublime.active_window()
        if window and window.folders():
            return window.folders()[0]
        return None
    
    def get_port_for_project(self, project_path):
        """Get the current port for a project"""
        if project_path in self.projects:
            return self.projects[project_path]['port']
        return None
    
    def get_current_port(self):
        """Get the port for the current project"""
        project_path = self.get_current_project()
        if not project_path or project_path not in self.projects:
            # Fall back to default port
            settings = DefoldSettings.get()
            return settings.get("default_port")
            
        return self.projects[project_path].get('port')
    
    def execute_command(self, command):
        """Execute a Defold command via HTTP API"""
        port = self.get_current_port()
        if not port:
            sublime.error_message("No Defold port available. Is Defold Editor running?")
            return False
            
        try:
            url = "http://localhost:{}/command/{}".format(port, command)
            print("Executing command: {}".format(url))
            req = urllib.request.Request(url, method="POST")
            with urllib.request.urlopen(req) as response:
                print("Command response status: {}".format(response.status))
                return response.status == 202
        except Exception as e:
            print("Error executing command: {}".format(e))
            sublime.error_message("Failed to execute command: {}".format(str(e)))
            return False
    
    def start_extender_server(self):
        """Start the extender server"""
        global EXTENDER_RUNNING
        if EXTENDER_RUNNING:
            print("Extender server is already running")
            return True
            
        settings = DefoldSettings.get()
        script_path = settings.get("extender_server_script")
        
        if not script_path:
            sublime.error_message("Extender server script path is not configured.")
            return False
            
        if not os.path.exists(script_path):
            sublime.error_message("Extender server script not found at: {}".format(script_path))
            return False
            
        try:
            print("Starting extender server: {}".format(script_path))
            os.chmod(script_path, 0o755)  # Ensure script is executable
            
            # Simple approach without trying to capture output
            result = subprocess.call([script_path, "start"])
            
            if result != 0:
                sublime.error_message("Failed to start extender server. Return code: {}".format(result))
                return False
                
            EXTENDER_RUNNING = True
            print("Extender server started successfully")
            return True
            
        except Exception as e:
            print("Exception starting extender server: {}".format(e))
            sublime.error_message("Exception starting extender server: {}".format(str(e)))
            return False
    
    def stop_extender_server(self):
        """Stop the extender server"""
        global EXTENDER_RUNNING
        if not EXTENDER_RUNNING:
            print("Extender server is not running")
            return True
            
        settings = DefoldSettings.get()
        script_path = settings.get("extender_server_script")
        
        if not script_path or not os.path.exists(script_path):
            sublime.error_message("Extender server script not found")
            return False
            
        try:
            print("Stopping extender server: {}".format(script_path))
            os.chmod(script_path, 0o755)  # Ensure script is executable
            
            # Simple approach without trying to capture output
            result = subprocess.call([script_path, "stop"])
            
            if result != 0:
                sublime.error_message("Failed to stop extender server. Return code: {}".format(result))
                return False
                
            EXTENDER_RUNNING = False
            print("Extender server stopped successfully")
            return True
            
        except Exception as e:
            print("Exception stopping extender server: {}".format(e))
            sublime.error_message("Exception stopping extender server: {}".format(str(e)))
            return False
    
    def restart_extender_server(self):
        """Restart the extender server"""
        global EXTENDER_RUNNING
        
        settings = DefoldSettings.get()
        script_path = settings.get("extender_server_script")
        
        if not script_path or not os.path.exists(script_path):
            sublime.error_message("Extender server script not found")
            return False
            
        try:
            print("Restarting extender server: {}".format(script_path))
            os.chmod(script_path, 0o755)  # Ensure script is executable
            
            # Simple approach without trying to capture output
            result = subprocess.call([script_path, "restart"])
            
            if result != 0:
                sublime.error_message("Failed to restart extender server. Return code: {}".format(result))
                return False
                
            EXTENDER_RUNNING = True
            print("Extender server restarted successfully")
            return True
            
        except Exception as e:
            print("Exception restarting extender server: {}".format(e))
            sublime.error_message("Exception restarting extender server: {}".format(str(e)))
            return False

# Command handler that executes Defold HTTP API commands
class DefoldCommandHandler(sublime_plugin.WindowCommand):
    def run(self, command):
        DefoldManager.instance().execute_command(command)
    
    def is_enabled(self):
        # Command is enabled if we have a port for the current project
        return DefoldManager.instance().get_current_port() is not None

# Extender server commands
class DefoldStartExtenderCommand(sublime_plugin.WindowCommand):
    def run(self):
        DefoldManager.instance().start_extender_server()

class DefoldStopExtenderCommand(sublime_plugin.WindowCommand):
    def run(self):
        DefoldManager.instance().stop_extender_server()

class DefoldRestartExtenderCommand(sublime_plugin.WindowCommand):
    def run(self):
        DefoldManager.instance().restart_extender_server()

# Status checking command
class DefoldCheckStatusCommand(sublime_plugin.WindowCommand):
    def run(self):
        manager = DefoldManager.instance()
        settings = DefoldSettings.get()
        
        # Get current project info
        current_project = manager.get_current_project()
        is_defold = current_project and manager.is_defold_project(current_project)
        current_port = None
        if is_defold and current_project in manager.projects:
            current_port = manager.projects[current_project]['port']
        
        # Build status message
        message = [
            "Defold Plugin Status:",
            "- Extender running: {}".format(EXTENDER_RUNNING),
            "- Current project: {}".format(current_project or 'None'),
            "- Is Defold project: {}".format(is_defold),
            "- Current port: {}".format(current_port or 'None'),
            "- Auto-start extender: {}".format(settings.get('auto_start_extender', False)),
            "- Extender script: {}".format(settings.get('extender_server_script', 'Not set')),
            "- Script exists: {}".format(os.path.exists(settings.get('extender_server_script', '')) if settings.get('extender_server_script') else False)
        ]
        
        # List all registered projects
        if manager.projects:
            message.append("\nRegistered projects:")
            for path, info in manager.projects.items():
                message.append("- {}: Port={}".format(path, info.get('port', 'None')))
        
        sublime.message_dialog("\n".join(message))

# Event listener for project detection
class DefoldEventListener(sublime_plugin.EventListener):
    def on_load_async(self, view):
        self._check_defold_project()
    
    def on_activated_async(self, view):
        self._check_defold_project()
    
    def on_pre_close_window(self, window):
        if window and window.folders():
            project_path = window.folders()[0]
            DefoldManager.instance().unregister_project(project_path)
    
    def _check_defold_project(self):
        window = sublime.active_window()
        if not window or not window.folders():
            return
            
        project_path = window.folders()[0]
        DefoldManager.instance().register_project(project_path)

def plugin_loaded():
    print("Defold plugin loaded")
    
    # Ensure we have default settings
    default_settings = {
        "default_port": None,
        "extender_server_script": "",
        "auto_start_extender": False
    }
    
    settings = DefoldSettings.get()
    for key, value in default_settings.items():
        if settings.get(key) is None:
            settings.set(key, value)
    DefoldSettings.save()
    
    # Register all open projects
    for window in sublime.windows():
        if window.folders():
            project_path = window.folders()[0]
            DefoldManager.instance().register_project(project_path)
    
    # Check if we need to auto-start extender
    if settings.get("auto_start_extender", False):
        print("Auto-starting extender during plugin initialization")
        # Use a delay to ensure everything is loaded
        sublime.set_timeout(
            lambda: DefoldManager.instance().start_extender_server(), 
            2000
        )

def plugin_unloaded():
    print("Defold plugin unloaded")
    
    # Stop all port watchers
    manager = DefoldManager.instance()
    for project_path in list(manager.projects.keys()):
        manager.unregister_project(project_path)
    
    # Stop extender if it was started by this plugin
    global EXTENDER_RUNNING
    settings = DefoldSettings.get()
    if settings.get("auto_start_extender", False) and EXTENDER_RUNNING:
        print("Stopping extender during plugin unload")
        manager.stop_extender_server()
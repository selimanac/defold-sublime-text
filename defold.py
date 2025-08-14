import sublime
import sublime_plugin
import subprocess
import os
import threading
import time
import urllib.request
import urllib.error

class DefoldManager(sublime_plugin.EventListener):
    _instance = None
    service_started = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DefoldManager, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    @classmethod
    def instance(cls):
        return cls()
    
    def initialize(self):
        """Initialize the manager"""
        self.projects = {}
        self.current_project_path = ""
        self.script_path = None
        print("DefoldManager initialized")
    
    def on_activated_async(self, view):
        # Get current project path
        project_path = self.get_project_path()
        
        if not project_path:
            return
            
        # First time setup
        if not self.service_started:
            self.service_started = True
            self.current_project_path = project_path

            # Get script path from settings
            settings = sublime.load_settings("Defold.sublime-settings")
            self.script_path = settings.get("extender_server_script")
            
            if not self.script_path or not os.path.exists(self.script_path):
                print("Extender script not configured or not found")
                return

            # Setup port watcher
            self._setup_port_watcher(project_path)

            # Start the service
            if settings.get("auto_start_extender", False):
                self.run_service_command("start")
        
        # Project changed, update port
        elif project_path != self.current_project_path:
            print("Project changed from '{}' to '{}'".format(self.current_project_path, project_path))
            self.current_project_path = project_path
            # Setup port watcher for new project
            self._setup_port_watcher(project_path)
    
    def _setup_port_watcher(self, project_path):
        """Setup a watcher for the editor.port file"""
        if not self.is_defold_project(project_path):
            return
            
        # Get the port file path
        port_file = os.path.join(project_path, ".internal", "editor.port")
        
        # Create the port directory if it doesn't exist
        port_dir = os.path.dirname(port_file)
        if not os.path.exists(port_dir):
            try:
                os.makedirs(port_dir)
            except Exception as e:
                print("Failed to create port directory: {}".format(e))
        
        # Store initial project info
        self.projects[project_path] = {
            'path': project_path,
            'port': None,
            'watcher': None
        }
        
        # Create a port file watcher
        def port_callback(port):
            if project_path in self.projects:
                self.projects[project_path]['port'] = port
                print("Updated port for {} to {}".format(project_path, port))
                
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
    
    def is_defold_project(self, project_path):
        """Check if a directory is a Defold project"""
        if not project_path:
            return False
            
        game_project_path = os.path.join(project_path, "game.project")
        result = os.path.exists(game_project_path)
        if result:
            print("Defold project detected: {}".format(project_path))
        return result
    
    def get_project_path(self):
        """Get the currently active project path"""
        folders = sublime.active_window().folders()
        return folders[0] if folders else ""
    
    def get_current_port(self):
        """Get the port for the current project"""
        project_path = self.current_project_path
        if not project_path or project_path not in self.projects:
            # Fall back to default port
            settings = sublime.load_settings("Defold.sublime-settings")
            return settings.get("default_port")
            
        return self.projects[project_path].get('port')
    
    def run_service_command(self, command):
        """Execute a service command"""
        if not self.script_path:
            settings = sublime.load_settings("Defold.sublime-settings")
            self.script_path = settings.get("extender_server_script")
            
        if not self.script_path or not os.path.exists(self.script_path):
            print("Extender script not configured or not found")
            return False
        
        try:
            print("Running service {} command".format(command))
            os.chmod(self.script_path, 0o755)  # Make executable
            subprocess.Popen([self.script_path, command])
            print("Service {} command executed".format(command))
            return True
        except Exception as e:
            print("Failed to {} service: {}".format(command, e))
            return False
    
    def on_exit(self):
        """Final cleanup when Sublime Text is shutting down"""
        if self.service_started:
            print("Stopping service on exit")
            self.run_service_command("stop")
            print("Service stopped on exit.")

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

# Command handler that executes Defold HTTP API commands
class DefoldCommandHandler(sublime_plugin.WindowCommand):
    def run(self, command):
        port = DefoldManager.instance().get_current_port()
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
            return False

# Extender server commands
class DefoldStartExtenderCommand(sublime_plugin.WindowCommand):
    def run(self):
        DefoldManager.instance().run_service_command("start")
        DefoldManager.instance().service_started = True

class DefoldStopExtenderCommand(sublime_plugin.WindowCommand):
    def run(self):
        DefoldManager.instance().run_service_command("stop")
        DefoldManager.instance().service_started = False

class DefoldRestartExtenderCommand(sublime_plugin.WindowCommand):
    def run(self):
        DefoldManager.instance().run_service_command("restart")
        DefoldManager.instance().service_started = True

# Status checking command
class DefoldCheckStatusCommand(sublime_plugin.WindowCommand):
    def run(self):
        manager = DefoldManager.instance()
        settings = sublime.load_settings("Defold.sublime-settings")
        
        # Get current project info
        current_project = manager.current_project_path
        is_defold = manager.is_defold_project(current_project)
        current_port = None
        if current_project and current_project in manager.projects:
            current_port = manager.projects[current_project].get('port')
        
        # Build status message
        message = [
            "Defold Plugin Status:",
            "- Extender tracking: {}".format("RUNNING" if manager.service_started else "STOPPED"),
            "- Current project: {}".format(current_project or 'None'),
            "- Is Defold project: {}".format(is_defold),
            "- Current port: {}".format(current_port or 'None'),
            "- Auto-start extender: {}".format(settings.get('auto_start_extender', False)),
            "- Extender script: {}".format(settings.get('extender_server_script', 'Not set'))
        ]
        
        # List all registered projects
        if manager.projects:
            message.append("\nRegistered projects:")
            for path, info in manager.projects.items():
                message.append("- {}: Port={}".format(path, info.get('port', 'None')))
        
        sublime.message_dialog("\n".join(message))

def plugin_loaded():
    print("Defold plugin loaded")
    
    # Ensure we have default settings
    default_settings = {
        "default_port": None,
        "extender_server_script": "",
        "auto_start_extender": False
    }
    
    settings = sublime.load_settings("Defold.sublime-settings")
    for key, value in default_settings.items():
        if settings.get(key) is None:
            settings.set(key, value)
    sublime.save_settings("Defold.sublime-settings")

def plugin_unloaded():
    print("Defold plugin unloaded")
    
    # Stop extender if running
    manager = DefoldManager.instance()
    if manager.service_started:
        print("Stopping extender during plugin unload")
        manager.run_service_command("stop")
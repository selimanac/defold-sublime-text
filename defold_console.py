import sublime
import sublime_plugin
import json
import urllib.request
import urllib.error
import threading
import time
import os
import re

class DefoldConsole:
    _instance = None
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = DefoldConsole()
        return cls._instance
    
    def __init__(self):
        self.panel = None
        self.auto_refresh = False
        self.refresh_thread = None
        self.refresh_interval = 2.0  # seconds
        self.panel_lock = threading.Lock()
        self.resource_regions = {}  # Store resource regions for navigation
    
    def get_panel(self, window):
        """Get or create the console output panel"""
        if not self.panel:
            self.panel = window.create_output_panel("defold_console")
            self.panel.settings().set("word_wrap", True)
            self.panel.settings().set("line_numbers", False)
            self.panel.settings().set("gutter", False)
            self.panel.settings().set("scroll_past_end", False)
            self.panel.assign_syntax("Packages/Defold/Defold Console.sublime-syntax")
        return self.panel
    
    def fetch_console(self, port):
        """Fetch console data from the editor"""
        if not port:
            return None
            
        try:
            url = "http://localhost:{}/console".format(port)
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data
        except Exception as e:
            print("Error fetching console data: {}".format(e))
            return None
    
    def update_panel(self, window, port):
        """Update the console panel with data from the editor"""
        data = self.fetch_console(port)
        if not data:
            return False
            
        with self.panel_lock:
            panel = self.get_panel(window)
            # Clear previous resource regions
            self.resource_regions = {}
            panel.run_command("defold_update_console_content", {
                "lines": data.get("lines", []),
                "regions": data.get("regions", [])
            })
            # Store resource regions in the panel's settings
            panel.settings().set("defold_resource_regions", self.resource_regions)
            
        return True
    
    def start_auto_refresh(self, window, port):
        """Start auto-refreshing the console"""
        if self.refresh_thread and self.refresh_thread.is_alive():
            return  # Already running
            
        self.auto_refresh = True
        
        def refresh_loop():
            while self.auto_refresh:
                sublime.set_timeout(lambda: self.update_panel(window, port), 0)
                time.sleep(self.refresh_interval)
        
        self.refresh_thread = threading.Thread(target=refresh_loop)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()
    
    def stop_auto_refresh(self):
        """Stop auto-refreshing the console"""
        self.auto_refresh = False
        if self.refresh_thread:
            self.refresh_thread.join(timeout=1.0)
            self.refresh_thread = None
    
    def add_resource_region(self, region, resource_path, line_number=None):
        """Store resource region for navigation"""
        key = "{},{}".format(region.a, region.b)
        self.resource_regions[key] = {"path": resource_path, "line": line_number}
    
    def get_resource_at_point(self, point):
        """Get resource info at the given point"""
        for region_str, info in self.resource_regions.items():
            start, end = map(int, region_str.split(','))
            region = sublime.Region(start, end)
            if region.contains(point):
                return info
        return None

class DefoldUpdateConsoleContentCommand(sublime_plugin.TextCommand):
    def run(self, edit, lines=None, regions=None):
        """Update the view content with console data"""
        if lines is None:
            lines = []
        if regions is None:
            regions = []
            
        # Clear the view
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        
        # Add the lines
        content = "\n".join(lines)
        self.view.insert(edit, 0, content)
        
        # Process the regions for styling
        self._process_regions(regions)
        
        # Also look for error lines that may not be in the regions
        self._process_error_lines(lines)
    
    def _process_regions(self, regions):
        """Process and style console regions"""
        # Clear all regions
        self.view.erase_regions("defold_error")
        self.view.erase_regions("defold_warning")
        self.view.erase_regions("defold_info")
        self.view.erase_regions("defold_repeat")
        self.view.erase_regions("defold_resource")
        
        error_regions = []
        warning_regions = []
        info_regions = []
        repeat_regions = []
        resource_regions = []
        
        console = DefoldConsole.instance()
        
        # Create style regions
        for region in regions:
            region_type = region.get("type", "")
            from_pos = region.get("from", {})
            to_pos = region.get("to", {})
            
            if not from_pos or not to_pos:
                continue
                
            # Convert row/col to character position
            start_row = from_pos.get("row", 0)
            start_col = from_pos.get("col", 0)
            end_row = to_pos.get("row", 0)
            end_col = to_pos.get("col", 0)
            
            start_point = self.view.text_point(start_row, start_col)
            end_point = self.view.text_point(end_row, end_col)
            region_obj = sublime.Region(start_point, end_point)
            
            if region_type == "eval-error" or region_type == "extension-error":
                error_regions.append(region_obj)
            elif region_type == "repeat":
                repeat_regions.append(region_obj)
            elif region_type == "resource-reference":
                resource_regions.append(region_obj)
                
                # Get the resource path for navigation
                path_candidates = region.get("proj-path-candidates", [])
                if path_candidates:
                    # Get path and row from the resource
                    resource_path = path_candidates[0]
                    line_number = region.get("row")
                    # Store for later navigation
                    console.add_resource_region(region_obj, resource_path, line_number)
            else:
                info_regions.append(region_obj)
        
        # Apply styles
        if error_regions:
            self.view.add_regions("defold_error", error_regions, "invalid", "", sublime.DRAW_NO_FILL)
        if warning_regions:
            self.view.add_regions("defold_warning", warning_regions, "string", "", sublime.DRAW_NO_FILL)
        if info_regions:
            self.view.add_regions("defold_info", info_regions, "comment", "", sublime.DRAW_NO_FILL)
        if repeat_regions:
            self.view.add_regions("defold_repeat", repeat_regions, "support.function", "", sublime.DRAW_NO_FILL)
        if resource_regions:
            self.view.add_regions("defold_resource", resource_regions, "entity.name.function", "", 
                                 sublime.DRAW_NO_FILL | sublime.DRAW_SOLID_UNDERLINE)
    
    def _process_error_lines(self, lines):
        """Scan for error lines that may not be in regions"""
        console = DefoldConsole.instance()
        
        # Regex patterns for common error formats
        patterns = [
            r'ERROR:.*?([^/\s]+/[^/\s]+/[^:]+):(\d+)',  # ERROR: path/file.ext:line
            r'([^/\s]+/[^/\s]+/[^:]+):(\d+):',  # path/file.ext:line:
            r'<([^/\s]+/[^/\s]+/[^>]+):(\d+)>',  # <path/file.ext:line>
        ]
        
        # Check each line
        for line_idx, line in enumerate(lines):
            for pattern in patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    if len(match) >= 2:
                        file_path, line_number = match
                        try:
                            line_num = int(line_number)
                            
                            # Find the region in the text
                            start = line.find(file_path)
                            if start >= 0:
                                start_point = self.view.text_point(line_idx, start)
                                end_point = start_point + len(file_path) + len(line_number) + 1  # +1 for the colon
                                region = sublime.Region(start_point, end_point)
                                
                                # Store for navigation
                                console.add_resource_region(region, file_path, line_num)
                                
                                # Add highlighting
                                existing_regions = self.view.get_regions("defold_resource")
                                existing_regions.append(region)
                                self.view.add_regions("defold_resource", existing_regions, 
                                                    "entity.name.function", "",
                                                    sublime.DRAW_NO_FILL | sublime.DRAW_SOLID_UNDERLINE)
                        except ValueError:
                            pass

class DefoldShowConsoleCommand(sublime_plugin.WindowCommand):
    def run(self):
        # Get the current port
        from .defold import DefoldManager
        port = DefoldManager.instance().get_current_port()
        if not port:
            sublime.error_message("No Defold port available. Is Defold Editor running?")
            return
            
        # Update and show the console
        console = DefoldConsole.instance()
        if console.update_panel(self.window, port):
            self.window.run_command("show_panel", {"panel": "output.defold_console"})
            # Start auto-refresh
            console.start_auto_refresh(self.window, port)

class DefoldRefreshConsoleCommand(sublime_plugin.WindowCommand):
    def run(self):
        # Get the current port
        from .defold import DefoldManager
        port = DefoldManager.instance().get_current_port()
        if not port:
            sublime.error_message("No Defold port available. Is Defold Editor running?")
            return
            
        # Update the console
        DefoldConsole.instance().update_panel(self.window, port)

class DefoldConsoleEventListener(sublime_plugin.EventListener):
    def on_text_command(self, view, command_name, args):
        """Handle click events in the console panel"""
        if view.name() != "output.defold_console" or command_name != "drag_select":
            return None
            
        # Check if this is a mouse click
        if "event" not in args:
            return None
            
        event = args["event"]
        point = view.window_to_text((event["x"], event["y"]))
        
        # Check if point is within a resource reference region
        console = DefoldConsole.instance()
        resource_info = console.get_resource_at_point(point)
        
        if resource_info:
            # Get the project path
            from .defold import DefoldManager
            project_path = DefoldManager.instance().get_current_project()
            if project_path:
                # Build the full file path
                file_path = os.path.normpath(os.path.join(project_path, resource_info["path"]))
                
                # Open the file at the specified line
                window = view.window()
                if window:
                    file_view = window.open_file(file_path)
                    if resource_info["line"] is not None:
                        # Use the transient flag so the focus stays in the console
                        # until the user explicitly switches to the file
                        window.open_file("{}:{}".format(file_path, resource_info["line"]), 
                                         sublime.ENCODED_POSITION)
                    return ("noop", None)  # Prevent default behavior
        
        return None
    
    def on_deactivated(self, view):
        """Stop auto-refresh when leaving the console panel"""
        if view.name() == "output.defold_console":
            DefoldConsole.instance().stop_auto_refresh()

def plugin_unloaded():
    """Clean up when the plugin is unloaded"""
    DefoldConsole.instance().stop_auto_refresh()
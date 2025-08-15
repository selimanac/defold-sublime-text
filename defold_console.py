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
        # Get refresh interval from settings with fallback to 2.0 seconds
        settings = sublime.load_settings("Defold.sublime-settings")
        self.refresh_interval = settings.get("console_refresh_interval", 2.0)  
        self.panel_lock = threading.Lock()
        self.phantom_set = None  # Restore phantom set
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
            # Create phantom set for this panel
            self.phantom_set = sublime.PhantomSet(self.panel, "defold_resource_links")
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
            
            # Check if view is scrolled to the bottom before updating
            visible_region = panel.visible_region()
            last_line_visible = False
            
            if panel.size() > 0:
                last_line_region = panel.line(panel.size() - 1)
                last_line_visible = visible_region.contains(panel.size() - 1) or visible_region.intersects(last_line_region)
            
            # Store current viewport position
            viewport_position = panel.viewport_position()
            
            # Clear previous resource regions
            self.resource_regions = {}
            panel.run_command("defold_update_console_content", {
                "lines": data.get("lines", []),
                "regions": data.get("regions", []),
                "auto_scroll": last_line_visible
            })
            
            # Store resource regions in the panel's settings
            panel.settings().set("defold_resource_regions", self.resource_regions)
            
            # Add clickable triangles
            self.add_clickable_resources(window, panel)
            
            # If view wasn't at the bottom before, restore viewport position
            if not last_line_visible:
                panel.set_viewport_position(viewport_position, False)
            
        return True
        
    def add_clickable_resources(self, window, view):
        """Add clickable phantoms over resource references"""
        # Get all resource regions
        resource_regions = view.get_regions("defold_resource")
        
        # Get project path - directly from window folders
        project_path = ""
        if window and window.folders():
            project_path = window.folders()[0]
        
        if not project_path:
            print("No project path found")
            return
        
        # Create phantoms for each resource region
        phantoms = []
        for region in resource_regions:
            # Get the text of the resource reference
            text = view.substr(region)
            
            # Parse path and line
            file_path = text
            line_number = None
            
            # Check if it has a line number
            if ':' in text:
                parts = text.split(':')
                file_path = parts[0]
                try:
                    line_number = int(parts[1])
                except ValueError:
                    pass
            
            # Create a phantom with a click handler
            html = '<a href="open:{}">▶</a>'.format(text)
            phantom = sublime.Phantom(
                region,
                html,
                sublime.LAYOUT_INLINE,
                lambda url, path=file_path, line=line_number, project=project_path: 
                    self.open_file(project, path, line)
            )
            phantoms.append(phantom)
        
        # Update the phantom set
        if self.phantom_set:
            self.phantom_set.update(phantoms)
    
    def open_file(self, project_path, file_path, line_number=None):
        """Open a file at the given line number"""
        try:
            window = sublime.active_window()
            if not window:
                print("No active window")
                return
                
            full_path = os.path.normpath(os.path.join(project_path, file_path))
            
            print("Opening file: {}".format(full_path))
            if line_number is not None:
                print("At line: {}".format(line_number))
                target = "{}:{}".format(full_path, line_number)
                window.open_file(target, sublime.ENCODED_POSITION)
            else:
                window.open_file(full_path)
                
        except Exception as e:
            print("Error opening file: {}".format(e))
    
    def start_auto_refresh(self, window, port):
        """Start auto-refreshing the console"""
        if self.refresh_thread and self.refresh_thread.is_alive():
            return  # Already running
        
        # Update refresh interval from settings
        settings = sublime.load_settings("Defold.sublime-settings")
        self.refresh_interval = settings.get("console_refresh_interval", 2.0)
            
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
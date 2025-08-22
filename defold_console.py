import sublime
import sublime_plugin
import json
import urllib.request
import urllib.error
import threading
import time
import os
import sys
import socket
from typing import Dict, Optional, List, Any

class DefoldConsole:
    _instance = None
    
    @classmethod
    def instance(cls): 
        """Get singleton instance of DefoldConsole"""
        if cls._instance is None:
            cls._instance = DefoldConsole()
        return cls._instance
    
    def __init__(self):
        """Initialize the console"""
        self.panel: Optional[sublime.View] = None
        self.auto_refresh: bool = False
        self.refresh_thread: Optional[threading.Thread] = None
        # Get refresh interval from settings with fallback to 2.0 seconds
        settings = sublime.load_settings("Defold.sublime-settings")
        self.refresh_interval: float = settings.get("console_refresh_interval", 2.0)  
        self.panel_lock = threading.Lock()
        self.phantom_set: Optional[sublime.PhantomSet] = None
        self.resource_regions: Dict[str, Dict[str, Any]] = {}
        # Add a max lines setting
        self.max_lines: int = settings.get("console_max_lines", 1000)
        # Add throttling for high-volume updates
        self._last_update: float = 0
        # Minimum time between updates in seconds
        self._throttle_time: float = 0.1
    
    def get_panel(self, window: sublime.Window) -> Optional[sublime.View]:
        """Get or create the console output panel"""
        if self.panel is None:
            # Create a new panel
            self.panel = window.create_output_panel("defold_console")
            if self.panel:  # Check if panel was created successfully
                self.panel.settings().set("word_wrap", True)
                self.panel.settings().set("line_numbers", False)
                self.panel.settings().set("gutter", False)
                self.panel.settings().set("scroll_past_end", False)
                self.panel.assign_syntax("Packages/Defold/Defold Console.sublime-syntax")
                # Create phantom set for this panel
                self.phantom_set = sublime.PhantomSet(self.panel, "defold_resource_links")
        return self.panel
    
    def is_port_available(self, port: int) -> bool:
        """Check if a port is available before attempting connection"""
        if not port:
            return False
            
        try:
            # Create a socket and try to connect to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)  # Short timeout
            result = sock.connect_ex(('localhost', port))
            sock.close()
            
            # If result is 0, the connection succeeded (port is in use)
            return result == 0
        except (socket.error, OSError):
            return False
    
    def fetch_console(self, port: Optional[int]) -> Optional[Dict]:
        """Fetch console data from the editor"""
        if not port:
            return None
            
        # First check if port is available before attempting connection
        if not self.is_port_available(port):
            return None
            
        try:
            request_url = f"http://localhost:{port}/console"
            req = urllib.request.Request(request_url)
            with urllib.request.urlopen(req, timeout=1.0) as response:  # Add timeout
                data = json.loads(response.read().decode('utf-8'))
                return data
        except urllib.error.URLError as e:
            # Quiet fail on connection errors
            pass
        except socket.timeout:
            # Quiet fail on timeouts
            pass
        except Exception as e:
            print(f"Error fetching console data: {e}")
        return None

    def is_console_visible(self, window: sublime.Window) -> bool:
        """Check if the console panel is currently visible"""
        if not window:
            return False
        
        # Get all visible panels in the window
        visible_panels = window.panels()
        return "output.defold_console" in visible_panels
    
    def update_panel(self, window: sublime.Window, port: Optional[int]) -> bool:
        """Update the console panel with data from the editor"""
        # Apply throttling for high-volume updates
        current_time = time.time()
        if (current_time - self._last_update) < self._throttle_time:
            return False  # Skip this update, too soon after last one
        self._last_update = current_time
            
        # Check if the console is visible before fetching data
        if not self.is_console_visible(window):
            # Console not visible, don't waste resources
            self.stop_auto_refresh()  # Stop refresh if panel is not visible
            return False
            
        if not (data := self.fetch_console(port)):
            return False
            
        with self.panel_lock:
            panel = self.get_panel(window)
            if not panel:  # Guard against None
                print("Could not create console panel")
                return False
                
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
            
            # Limit the number of lines to display
            lines = data.get("lines", [])
            if len(lines) > self.max_lines:
                lines = lines[-self.max_lines:]
                # Add a note at the beginning indicating lines were truncated
                lines.insert(0, f"[Defold Console] Output truncated. Showing last {self.max_lines} lines.")
            
            # Filter regions to match our limited lines
            regions = []
            if data.get("regions"):
                for region in data.get("regions", []):
                    from_row = region.get("from", {}).get("row", 0)
                    if from_row < len(lines):
                        regions.append(region)
            
            panel.run_command("defold_update_console_content", {
                "lines": lines,
                "regions": regions,
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
        
    def add_clickable_resources(self, window: sublime.Window, view: sublime.View) -> None:
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
            html = f'<a href="open:{text}">▶</a>'
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
    
    def open_file(self, project_path: str, file_path: str, line_number: Optional[int] = None) -> None:
        """Open a file at the given line number"""
        try:
            if not (window := sublime.active_window()):
                print("No active window")
                return
                
            full_path = os.path.normpath(os.path.join(project_path, file_path))
            
            print(f"Opening file: {full_path}")
            if line_number is not None:
                print(f"At line: {line_number}")
                target = f"{full_path}:{line_number}"
                window.open_file(target, sublime.ENCODED_POSITION)
            else:
                window.open_file(full_path)
                
        except Exception as e:
            print(f"Error opening file: {e}")
    
    def start_auto_refresh(self, window: sublime.Window, port: Optional[int]) -> None:
        """Start auto-refreshing the console"""
        if self.refresh_thread and self.refresh_thread.is_alive():
            return  # Already running
        
        # Update refresh interval from settings
        settings = sublime.load_settings("Defold.sublime-settings")
        self.refresh_interval = settings.get("console_refresh_interval", 2.0)
        self.max_lines = settings.get("console_max_lines", 1000)
            
        self.auto_refresh = True
        
        def refresh_loop() -> None:
            """Thread main loop for console refresh"""
            while self.auto_refresh:
                # Only update if the console is visible
                if window and self.is_console_visible(window):
                    sublime.set_timeout(lambda: self.update_panel(window, port), 0)
                # If console is not visible, no need to continue refreshing
                elif window:
                    self.stop_auto_refresh()
                    break
                time.sleep(self.refresh_interval)
        
        self.refresh_thread = threading.Thread(target=refresh_loop)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()
    
    def stop_auto_refresh(self) -> None:
        """Stop auto-refreshing the console"""
        self.auto_refresh = False
        if self.refresh_thread and self.refresh_thread.is_alive():
            try:
                self.refresh_thread.join(timeout=1.0)
                self.refresh_thread = None
            except RuntimeError as e:
                print(f"Error stopping refresh thread: {e}")
    
    def add_resource_region(self, region: sublime.Region, resource_path: str, line_number: Optional[int] = None) -> None:
        """Store resource region for navigation"""
        key = f"{region.a},{region.b}"
        resource_info: Dict[str, Any] = {"path": resource_path}
        if line_number is not None:
            resource_info["line"] = line_number
        self.resource_regions[key] = resource_info
    
    def get_resource_at_point(self, point: int) -> Optional[Dict[str, Any]]:
        """Get resource info at the given point"""
        for region_str, info in self.resource_regions.items():
            start, end = map(int, region_str.split(','))
            region = sublime.Region(start, end)
            if region.contains(point):
                return info
        return None

class DefoldUpdateConsoleContentCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, lines: List[str], regions: List[Dict], auto_scroll: bool = True) -> None:
        """Update the console content with new lines and regions"""
        view = self.view
        
        # Clear the view
        view.erase(edit, sublime.Region(0, view.size()))
        
        # Insert the new lines
        for line in lines:
            view.insert(edit, view.size(), line + '\n')
            
        # Process regions to find resource references
        resource_regions = []
        for region in regions:
            from_row = region.get("from", {}).get("row", 0)
            from_col = region.get("from", {}).get("col", 0)
            to_row = region.get("to", {}).get("row", 0)
            to_col = region.get("to", {}).get("col", 0)
            region_type = region.get("type", "")
            
            # Look for resource references
            if region_type == "resource-reference" and "proj-path-candidates" in region:
                # Get region bounds in the view
                start_point = view.text_point(from_row, from_col)
                end_point = view.text_point(to_row, to_col)
                region_obj = sublime.Region(start_point, end_point)
                resource_regions.append(region_obj)
                
                # Get the resource path
                resource_text = view.substr(region_obj)
                
                # Check if there's a line number
                line_number = None
                if "row" in region:
                    line_number = region.get("row")
                
                # Store resource reference for navigation
                console = DefoldConsole.instance()
                console.add_resource_region(region_obj, resource_text, line_number)
        
        # Add regions for resource references
        view.add_regions("defold_resource", resource_regions, "string", "bookmark", 
                        sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE)
                
        # Scroll to the end if requested
        if auto_scroll:
            view.show(view.size())

class DefoldShowConsoleCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        """Show the Defold console panel"""
        # Fix: use sys.modules to get the defold module
        defold_module = None
        for module_name in sys.modules:
            if module_name.endswith("defold"):
                defold_module = sys.modules[module_name]
                break
                
        if not defold_module:
            sublime.error_message("Could not find defold module")
            return
            
        window = self.window
        console = DefoldConsole.instance()
        console_panel = console.get_panel(window)
        
        # Show the panel
        if console_panel:
            window.run_command("show_panel", {"panel": "output.defold_console"})
            
            # Get the current port and refresh the console
            port = defold_module.DefoldManager.instance().get_current_port()
            if port:
                console.update_panel(window, port)
                console.start_auto_refresh(window, port)
        else:
            sublime.error_message("Failed to create console panel")

class DefoldRefreshConsoleCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        """Manually refresh the console content"""
        # Fix: use sys.modules to get the defold module
        defold_module = None
        for module_name in sys.modules:
            if module_name.endswith("defold"):
                defold_module = sys.modules[module_name]
                break
                
        if not defold_module:
            sublime.error_message("Could not find defold module")
            return
            
        window = self.window
        console = DefoldConsole.instance()
        port = defold_module.DefoldManager.instance().get_current_port()
        if port:
            console.update_panel(window, port)

class DefoldClearConsoleCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        """Clear the console content"""
        console = DefoldConsole.instance()
        console_panel = console.get_panel(self.window)
        if console_panel:
            console_panel.run_command("defold_update_console_content", {
                "lines": [],
                "regions": [],
                "auto_scroll": True
            })
            print("Defold console cleared")
        else:
            print("No console panel to clear")

class DefoldConsolePanelListener(sublime_plugin.EventListener):
    def on_hide_panel(self, window, panel_name):
        """Stop refreshing when the panel is hidden"""
        if panel_name == "output.defold_console":
            print("Defold console panel hidden, stopping auto-refresh")
            DefoldConsole.instance().stop_auto_refresh()
import sublime
import sublime_plugin

class DefoldCheckAnnotationsCommand(sublime_plugin.WindowCommand):
    def run(self):
        from .defold_annotations import DefoldAnnotationsManager
        
        # Show status message
        self.window.status_message("Checking for Defold annotations updates...")
        
        def on_complete(message, version):
            self.window.status_message(message)
        
        # Start the update check
        DefoldAnnotationsManager.check_and_update(on_complete)
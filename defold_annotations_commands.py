import sublime
import sublime_plugin

class DefoldCheckAnnotationsCommand(sublime_plugin.WindowCommand):
    def run(self):
        # Changed from relative to absolute import
        import defold_annotations
        
        # Show status message
        self.window.status_message("Checking for Defold annotations updates...")
        
        def on_complete(message, version):
            self.window.status_message(message)
        
        # Start the update check
        defold_annotations.DefoldAnnotationsManager.check_and_update(on_complete)
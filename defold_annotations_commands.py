import sublime
import sublime_plugin
import os


class DefoldCheckAnnotationsCommand(sublime_plugin.WindowCommand):
    def run(self):
        """Check for annotations updates"""
        # Get the path to the annotations module
        module_path = os.path.join(os.path.dirname(__file__), "defold_annotations.py")
        
        # Use direct globals access (THIS WORKS IN SUBLIME TEXT PLUGINS)
        module_globals = {}
        with open(module_path, 'r') as f:
            exec(f.read(), module_globals)
        
        # Now we can access the class directly
        DefoldAnnotationsManager = module_globals['DefoldAnnotationsManager']
        
        def on_complete(message, version):
            if version:
                sublime.message_dialog(message)
            else:
                sublime.status_message(message)
        
        # Use the manager directly
        DefoldAnnotationsManager.check_and_update(on_complete)
        sublime.status_message("Checking for Defold annotations updates...")
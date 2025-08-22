import sublime
import sublime_plugin
import os
import importlib.util
import sys

def load_module(module_path, module_name):
    """Safely load a Python module from a file path"""
    # Security check - make sure module is inside packages path
    if not os.path.normpath(module_path).startswith(os.path.normpath(sublime.packages_path())):
        print(f"Security warning: Trying to load module outside packages directory: {module_path}")
        return None
        
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if not spec or not spec.loader:
            print(f"Could not create valid module spec for {module_path}")
            return None
            
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module 
        
        # Add explicit check that spec.loader is not None
        if spec.loader:
            spec.loader.exec_module(module)
            return module
        else:
            print(f"Module loader is None for {module_path}")
            return None
    except Exception as e:
        print(f"Error loading module {module_name} from {module_path}: {e}")
        return None

class DefoldCheckAnnotationsCommand(sublime_plugin.WindowCommand):
    def run(self):
        """Check for annotations updates"""
        # Get the path to the annotations module
        module_path = os.path.join(os.path.dirname(__file__), "defold_annotations.py")
        module_name = "defold_annotations"
        
        # Use improved module loading
        annotations_module = load_module(module_path, module_name)
        
        if not annotations_module or not hasattr(annotations_module, 'DefoldAnnotationsManager'):
            sublime.status_message("Failed to load annotations manager")
            return
            
        DefoldAnnotationsManager = annotations_module.DefoldAnnotationsManager
        
        def on_complete(message, version):
            if version:
                sublime.message_dialog(message)
            else:
                sublime.status_message(message)
        
        # Use the manager directly
        DefoldAnnotationsManager.check_and_update(on_complete)
        sublime.status_message("Checking for Defold annotations updates...")
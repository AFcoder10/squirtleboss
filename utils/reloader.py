import sys
import importlib

def reload_modules(prefix="utils"):
    """
    Reloads all modules in sys.modules that start with the given prefix.
    Returns a list of reloaded module names.
    """
    reloaded = []
    # Create a list of keys to avoid runtime error if dictionary changes size
    modules_to_reload = [
        (name, module) for name, module in sys.modules.items() 
        if name.startswith(prefix) and module is not None
    ]
    
    for name, module in modules_to_reload:
        try:
            importlib.reload(module)
            reloaded.append(name)
        except Exception as e:
            print(f"Failed to reload {name}: {e}")
            
    return reloaded

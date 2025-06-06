import os
import importlib.util
from typing import Dict, Any, Callable

class PluginManager:
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugins: Dict[str, Any] = {}
        self.plugin_dir = plugin_dir
        
        # Create plugins directory if it doesn't exist
        os.makedirs(plugin_dir, exist_ok=True)
        
    def load_plugins(self) -> None:
        """Load all plugins from the plugin directory"""
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                try:
                    self._load_plugin(filename)
                except Exception as e:
                    print(f"Error loading plugin {filename}: {str(e)}")
                    
    def _load_plugin(self, filename: str) -> None:
        """Load a single plugin from file"""
        name = filename[:-3]  # Remove .py extension
        file_path = os.path.join(self.plugin_dir, filename)
        
        spec = importlib.util.spec_from_file_location(name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load plugin {filename}")
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Validate plugin interface
        if not hasattr(module, "apply"):
            raise ValueError(f"Plugin {filename} missing required 'apply' function")
            
        self.plugins[name] = module
        
    def get_plugin(self, name: str) -> Any:
        """Get a plugin by name"""
        return self.plugins.get(name)
        
    def list_plugins(self) -> list:
        """List all available plugins"""
        return list(self.plugins.keys())
        
    def apply_plugin(self, name: str, *args, **kwargs) -> Any:
        """Apply a plugin to the given arguments"""
        plugin = self.get_plugin(name)
        if plugin is None:
            raise ValueError(f"Plugin {name} not found")
        return plugin.apply(*args, **kwargs)

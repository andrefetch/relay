import importlib.util
import inspect
from pathlib import Path
import sys
from typing import Any

from config.loader import get_config_dir
from tools import Tool

from config.config import Config
from tools.registry import ToolRegistry

class ToolDiscoveryManager:

    def __init__(
            self,
            config: Config,
            registery: ToolRegistry
    ):
        
        self.config = config
        self.registery = registery
    
    def _find_tool_classes(self, module: Any) -> list[Tool]:

        tools: list[Tool] = [] 

        for name in dir(module):
            obj = getattr(module, name)

            if inspect.isclass(obj) and issubclass(obj, Tool) and obj is not Tool and obj.__module__ == module.__name__:
                tools.append(obj)
        
        return tools

    
    def _load_tool_modules(self, file_path: Path) -> Any:

        module_name = f'discorvered_tool_{file_path.stem}' # will truncate the imports from file ending with py into just a norm
        spec = importlib.util.spec_from_file_location(module_name, file_path)

        if spec is None or spec.loader is None:
            return ImportError(
                f'Could not load spec from: {file_path}'
            )
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        spec.loader.exec_module(module)
        return module
    
    def discover_from_dir(self, directory: Path) -> None:

        tool_dir = directory / '.relay' / 'tools'

        if not tool_dir.exists() or not tool_dir.is_dir():
            return
        
        # Custom tools are only supported by python filetypes, no other languages.

        for py_file in tool_dir.glob('*.py'):
            
            try:
            
                # if file is a dunder file ex: __init__.py, just continue onto the next iteration
                if py_file.name.startswith('__'):
                    continue
                
                module = self._load_tool_modules(py_file)
                tool_classes = self._find_tool_classes(module)

                if not tool_classes:
                    continue

                for tool_class in tool_classes:
                    tool = tool_class(self.config)

                    self.registery.register(tool)
            
            except Exception as e:

                print(f'Error: {e}')
                continue
    
    def discover(self) -> None:
        
        self.discover_from_dir(self.config.cwd)
        self.discover_from_dir(get_config_dir())

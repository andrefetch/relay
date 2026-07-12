from tools.core.directories import ListDirectoriesTool
from tools.core.read import ReadFileTool
from tools.core.write_file import WriteFileTool
from tools.core.edit import EditTool
from tools.core.shell import ShellTool
from tools.core.grep import GrepTool
from tools.core.glob import GlobTool

from tools.network.search import WebSearchTool
from tools.network.fetch import WebFetchTool

from tools.base import Tool

__all__ = [
    'ReadFileTool',
    'WriteFileTool',
    'EditTool',
    'ShellTool',
    'ListDirectoriesTool',
    'GrepTool',
    'GlobTool',
    'WebSearchTool',
    'WebFetchTool',
]

def get_all_core_tools() -> list[Tool]:
    return [
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ShellTool,
        ListDirectoriesTool,
        GrepTool,
        GlobTool,
        WebSearchTool,
        WebFetchTool,
    ]

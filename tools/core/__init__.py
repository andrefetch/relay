from tools.core.directories import ListDirectoriesTool
from tools.core.read_file import ReadFileTool
from tools.core.write_file import WriteFileTool
from tools.core.edit_file import EditTool
from tools.core.shell import ShellTool
from tools.base import Tool

__all__ = [
    'ReadFileTool'
    'WriteFileTool'
    'EditTool'
    'ShellTool'
    'ListDirectoriesTool'
]

def get_all_core_tools() -> list[Tool]:
    return [
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ShellTool,
        ListDirectoriesTool,
    ]

from tools.core.read_file import ReadFileTool
from tools.core.write_file import WriteFileTool
from tools.core.edit_file import EditTool
from tools.base import Tool

__all__ = [
    'ReadFileTool'
    'WriteFileTool'
    'EditTool'
]

def get_all_core_tools() -> list[Tool]:
    return [
        ReadFileTool,
        WriteFileTool,
        EditTool
    ]

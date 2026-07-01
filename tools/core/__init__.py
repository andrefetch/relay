from tools.core.read_file import ReadFileTool
from tools.base import Tool

__all__ = [
    'ReadFileTool'
]

def get_all_core_tools() -> list[Tool]:
    return [
        ReadFileTool
    ]

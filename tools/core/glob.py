import os
from pathlib import Path
import re

from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field

from utils.paths import is_binary_file, resolve_path

class GlobParams(BaseModel):

    pattern: str = Field(
        ...,
        description='Glob pattern to match for.'
    )

    path: str = Field(
        '.',
        description='Directory path to search in (default: current directory)'
    )

class GlobTool(Tool):
    name = 'glob'
    description = 'Find files matching a glob pattern. Supports ** for recursive search and matching.'
    kind = ToolKind.READ
    schema = GlobParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = GlobParams(**invocation.params)

        search_path = resolve_path(invocation.cwd, params.path)\
        
        if not search_path.exists() or not search_path.is_dir():
            return ToolResult.error_result(
                f'Directory does not exist: {search_path}'
            )
        try:
            matches = list(search_path.glob(params.pattern))
            matches = [p for p in matches if p.is_file()]
        except Exception as e:
            return ToolResult.error_result(
                f'Error searching: {e}'
        )

        output_lines: list = []

        for file_path in matches[:1000]:

            try:
                relative_path = file_path.relative_to(
                    invocation.cwd
                )
            except Exception:
                relative_path = file_path
        
            output_lines.append(str(relative_path))

        if len(matches) > 1000:
            output_lines.append(f"...(limited to 1000 results)")
        return ToolResult.success_result(
            '\n'.join(output_lines),
            metadata = {
                'path': str(search_path),
                'matches': len(matches),
            }
        )
    
    def _find_files(self, search_path: Path) -> list[Path]:

        files = []
        
        for root, dirs, filenames in os.walk(search_path):
            dirs[:] = [
                d for d in dirs if d not in 
            {
                'node_modules',
                '__pycache__',
                '.git',
                '.venv',
                'venv',
            }
        ]
            for filename in filenames:
                if filename.startswith('.'):
                    continue
                
                file_path = Path(root) / filename
                if not is_binary_file(file_path):
                    files.append(file_path)
                    if len(files) >= 500:
                        return files
        
        return files
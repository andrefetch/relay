import os
from pathlib import Path
import re

from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field

from utils.paths import is_binary_file, resolve_path

class GrepParams(BaseModel):

    patten: str = Field(
        ...,
        description='Regular expression pattern to search for.'
    )

    path: str = Field(
        '.',
        description='File or Directory path to search in (default: current directory)'
    )
    
    case_insensitive: bool = Field(
        False,
        description="Case-insensitive search (default: false)"
    )

class GrepTool(Tool):
    name = 'grep'
    description = 'Searching for a regex pattern in the file content and will return the matching lines with file paths and line numbers.'
    kind = ToolKind.READ
    schema = GrepParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = GrepParams(**invocation.params)

        search_path = resolve_path(invocation.cwd, params.path)\
        
        if not search_path.exists() or not search_path.is_dir():
            return ToolResult.error_result(
                f'Path does not exist: {search_path}'
            )
        try:
            flags = re.IGNORECASE if params.case_insensitive else 0
            pattern = re.compile(params.pattern, flags)
        except re.error as e:
            return ToolResult.error_result(
                f'Invalid regex pattern: {e}'
        )

        if search_path.is_dir():
            files = self._find_files(search_path)
        else:
            files = [search_path]
        
        output_lines: list = []
        matches: int = 0

        for file_path in files:

            try:
                content = file_path.read_text(
                    encoding='utf-8'
                )
            except Exception:
                continue
        
            lines = content.splitlines()
            file_matches = False

            for i, line in enumerate(lines):
                if pattern.search(line):
                    matches += 1
                    if not file_matches:
                        relative_path = file_path.relative_to(invocation.cwd)
                        output_lines.append(f'┈┈ {relative_path} ┈┈')
                        file_matches = True
                    
                    output_lines.append(f"{i}:{line}")
            
            if file_matches:
                output_lines.append("")
        
        if not output_lines:

            return ToolResult.success_result(
                f'No matches found for pattern: {params.pattern}',
                metadata = {
                'path': str(search_path),
                'matches': 0,
                'files_searched': len(files)
                }
            )

        return ToolResult.success_result(
            '\n'.join(output_lines),
            metadata = {
                'path': str(search_path),
                'matches': matches,
                'files_searched': len(files)
            }
        )
    
    def _find_files(self, search_path: Path) -> list[Path]:

        files = []
        
        for root, dirs, filenames in os.walk(search_path):
            for filename in filenames:
                if filename.startswith('.'):
                    continue
                
                file_path = Path(root) / filename
                if not is_binary_file(file_path):
                    files.append(file_path)
                    if len(files) >= 500:
                        return files
        
        return files
from pydantic import BaseModel, Field
from utils.paths import resolve_path, is_binary_file
from utils.text import count_tokens, truncate_text
from tools.base import Tool, ToolKind, ToolInvocation, ToolResult

class ReadFileParams(BaseModel):

    path: str = Field(
        ...,
        description='Path to the file to read (relative to the working dir or abs path)'
    )

    offset: int = Field(
        1,
        ge=1,
        description='1-indexed line number to start reading from. Defaults to 1 (start of file). Minimum value is 1.'
    )

    limit: int | None = Field(
        None,
        description='Maximum number of lines to read starting from offset. If omitted, reads to the end of the file.'
    )

class ReadFileTool(Tool):
    name = 'read_file'
    description = (
        "Read the contents of a file from the filesystem and return it as text with line numbers prefixed "
        "(e.g. '1: import os'). If 'offset' exceeds the file's line count, returns an empty result. "
        "Fails if the file does not exist, is a directory, or cannot be read (e.g. binary/permission errors). "
        "Cannot read binary files (images, executables, etc.). "
        "After reading the contents of the file, present the line numbers."
    )
    kind = ToolKind.READ

    schema = ReadFileParams

    MAX_FILE_SIZE = 1024 * 1024 * 10
    MAX_OUTPUT_TOKENS = 25000

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ReadFileParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)

        if not path.exists():
            return ToolResult.error_result(f"File not found at: {path}")

        if not path.is_file():
            return ToolResult.error_result(f"Path is not a file: {path}")

        file_size = path.stat().st_size

        if file_size > self.MAX_FILE_SIZE:
            return ToolResult.error_result(
                f"File too large ({file_size / (1024 * 1024):.1f}MB). "
                f"The maximum file size is: {self.MAX_FILE_SIZE / (1024 * 1024):.0f}MB."
            )

        if is_binary_file(path):
            file_size_mb = file_size / (1024 * 1024)
            size_str = f"{file_size_mb:.2f}MB" if file_size_mb >= 1 else f"{file_size} bytes"
            return ToolResult.error_result(
                f"Cannot read binary file: {path.name} ({size_str}). "
                f"This tool only reads text files."
            )
        try:
            try:
                content = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                content = path.read_text(encoding='latin-1')

            lines = content.splitlines()
            total_lines = len(lines)

            if total_lines == 0:
                return ToolResult.success_result(
                    "File is empty.", metadata={
                        "lines": 0
                    }
                )

            start_index = max(0, params.offset - 1)

            if params.limit is not None:
                end_index = min(start_index + params.limit, total_lines)
            else:
                end_index = total_lines

            selected_lines = lines[start_index:end_index]
            formatted_lines = []

            for i, line in enumerate(selected_lines, start=start_index):
                formatted_lines.append(f"{i + 1:6}|{line}")

            output = "\n".join(formatted_lines)
            token_count = count_tokens(output, "poolside/laguna-xs-2.1:free")

            truncated = False
            if token_count > self.MAX_OUTPUT_TOKENS:
                output = truncate_text(
                    output,
                    self.MAX_OUTPUT_TOKENS,
                    suffix=f"\n... [truncated] {total_lines} total lines."
                )
                truncated = True

            metadata_lines = []
            if start_index > 0 or end_index < total_lines:
                metadata_lines.append(
                    f"Showing lines {start_index + 1}-{end_index} of {total_lines}"
                )

            if metadata_lines:
                header = ' | '.join(metadata_lines) + "\n\n"
                output = header + output

            return ToolResult.success_result(
                output=output,
                truncated=truncated,
                metadata={
                    'path': str(path),
                    'total_lines': total_lines,
                    'shown_start': start_index + 1,
                    'shown_end': end_index,
                },
            )
        except Exception as e:
            return ToolResult.error_result(f"Error: failed to read file: {e}")
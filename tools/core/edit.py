from pathlib import Path

from tools.base import FileDiff, Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field

from utils.paths import ensure_parent_dir, resolve_path

class EditParams(BaseModel):
    path: str = Field(
        ...,
        description='Path to the file to edit (relative to working directory) or an absolute path.'
    )
    old_string: str = Field(
        "",
        description='The exact text to find and replace and must match excatly including all whitespace and indentation, for new files this should be empty'
    )
    new_string: str = Field(
        ...,
        description='The text to replace old_string with. Can be empty to delete.'
    )
    replace_all: bool = Field(
        False,
        description='Replace all occurrences of old_string default is false'
    )

class EditTool(Tool):
    name = "edit"
    description = (
        "Edit a file by replacing text, the old_string variable must match exactly"
        "( including whitespace and indentation ) and must be unique in the file"
        "unless replace_all is true, use thsi for precise, surgical edits"
        "For creating new files or complete rewrites, use write instead"
    )
    kind = ToolKind.WRITE
    schema = EditParams # type: ignore

    async def execute(
            self, 
            invocation: ToolInvocation
    ) -> ToolResult:

        params = EditParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)

        if not path.exists():
            if params.old_string:
                return ToolResult.error_result(
                    f'File does not exist: {path}. To create a new file, use an empty old_string.'
                )

            ensure_parent_dir(path)
            path.write_text(params.new_string, encoding='utf-8')

            line_count = len(params.new_string.splitlines())

            return ToolResult.success_result(
                f'Created: {path} {line_count} lines',
                diff=FileDiff(
                    path=path,
                    old_content="",
                    new_content=params.new_string,
                    is_new_file=True,
                ),
                metadata = {
                    'path': str(path),
                    'is_new_file': True,
                    'lines': line_count
                }
            )
        
        old_content = path.read_text(encoding='utf-8')

        if not params.old_string:
            return ToolResult.error_result(
                'old_string is empty but file exists. Provide old_string to edit, or use write to overwrite the file.'
            )
        
        occurrence_count = old_content.count(params.old_string)

        if occurrence_count == 0:
            return self._no_match_error(params.old_string, old_content, path)
        
        if occurrence_count > 1 and not params.replace_all:
            return ToolResult.error_result(
                f"old_string found {occurrence_count} times in {path}. "
                f"Either: \n"
                f"1. Provide more context to make the match unique or\n"
                f"2. Set replace_all=true to replace all occurrences",
                metadata={
                    "occurence_count": occurrence_count,
                },
            )

        if params.replace_all:
            new_content = old_content.replace(params.old_string, params.new_string)
            replace_count = occurrence_count
        else:
            new_content = old_content.replace(params.old_string, params.new_string, 1)
            replace_count = 1

        if new_content == old_content:
            return ToolResult.error_result(
                "No change made - old_string equals new_string"
            )

        try:
            path.write_text(new_content, encoding="utf-8")
        except IOError as e:
            return ToolResult.error_result(f"failed to write file: {e}")

        old_lines = len(old_content.splitlines())
        new_lines = len(new_content.splitlines())
        line_diff = new_lines - old_lines

        diff_msg = ""

        if line_diff > 0:
            diff_msg = f" (+{line_diff} lines)"
        elif line_diff < 0:
            diff_msg = f" ({line_diff} lines)"

        return ToolResult.success_result(
            f"Edited {path}: replaced {replace_count} occurrence(s){diff_msg}",
            diff=FileDiff(path=path, old_content=old_content, new_content=new_content),
            metadata={
                "path": str(path),
                "replaced_count": replace_count,
                "line_diff": line_diff,
            },
        )

    def _no_match_error(self, old_string: str, content: str, path: Path) -> ToolResult:
        lines = content.splitlines()

        partial_matches = []
        search_terms = old_string.split()[:5]

        if search_terms:
            first_term = search_terms[0]
            for i, line in enumerate(lines, 1):
                if first_term in line:
                    partial_matches.append((i, line.strip()[:80]))
                    if len(partial_matches) >= 3:
                        break

        error_msg = f"old_string not found in {path}."

        if partial_matches:
            error_msg += "\n\nPossible similar lines:"
            for line_num, line_preview in partial_matches:
                error_msg += f"\n  Line {line_num}: {line_preview}"
            error_msg += "\n\nMake sure old_string matches exactly (including whitespace and indentation)."
        else:
            error_msg += (
                " Make sure the text matches exactly, including:\n"
                "- All whitespace and indentation\n"
                "- Line breaks\n"
                "- Any invisible characters\n"
                "Try re-reading the file using read tool and then editing."
            )

        return ToolResult.error_result(error_msg)
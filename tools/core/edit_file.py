from tools.base import Tool

class EditTool(Tool):
    name = "edit"
    description = (
        "Edit a file by replacing text, the old_string varaible must match exactly"
        "( including whitespace and indentation ) and must be unique in the file"
        "unless replace_all is true, use thsi for precise, surgical edits"
        "For creating new files or complete rewrites, use write_file instead"
    )
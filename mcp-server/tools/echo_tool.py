TOOL_NAME = "echo"
TOOL_DESCRIPTION = "Returns the input it was given. Reference template for new tools."
INPUT_SCHEMA = {
    "message": {"type": "string", "required": True}
}


def run(input: dict) -> dict:
    return {"echo": input.get("message")}
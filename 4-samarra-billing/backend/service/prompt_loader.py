from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_DIR = BASE_DIR / "prompts"


def load_prompt(filename):
    prompt_path = PROMPT_DIR / filename

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}"
        )

    return prompt_path.read_text(
        encoding="utf-8"
    ).strip()

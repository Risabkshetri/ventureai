import os

def load_prompt(filename: str) -> str:
    """Loads prompt content from the app/prompts/ directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "..", "prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()

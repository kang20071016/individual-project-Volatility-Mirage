"""Prompt locally for a DeepSeek key and save it outside Git."""

import getpass
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".streamlit" / "secrets.toml"


def main():
    ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    if ".streamlit/secrets.toml" not in ignore_rules:
        raise SystemExit("Secret target is not Git-ignored; refusing to write.")
    if TARGET.exists():
        existing = tomllib.loads(TARGET.read_text(encoding="utf-8"))
        if set(existing) != {"DEEPSEEK_API_KEY"}:
            raise SystemExit("secrets.toml contains other settings; edit it locally to preserve them.")
    key = getpass.getpass("DeepSeek API Key (input hidden): ").strip()
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{20,}", key):
        raise SystemExit("The value does not look like a DeepSeek API Key.")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(f'DEEPSEEK_API_KEY = "{key}"\n', encoding="utf-8")
    print("Saved DeepSeek key to Git-ignored Streamlit Secrets. Restart the app.")


if __name__ == "__main__":
    main()

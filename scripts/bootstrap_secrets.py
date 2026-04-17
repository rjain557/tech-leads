"""Populate scripts/secrets.json from the user's keys vault.

Reads markdown files in:
  C:/Users/<user>/OneDrive - Technijian, Inc/Documents/VSCODE/keys/

Writes ONLY the keys we currently need into scripts/secrets.json (gitignored).
Existing values are preserved; re-running is idempotent.
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SECRETS = HERE / "secrets.json"

KEYS_DIR = Path(os.environ["USERPROFILE"]) / "OneDrive - Technijian, Inc" / "Documents" / "VSCODE" / "keys"


def parse_md(path: Path) -> dict[str, str]:
    """Extract `**Label:** value` pairs from a markdown key file."""
    text = path.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"\*\*([^*]+):\*\*\s*(\S.*?)\s*$", text, re.MULTILINE):
        out[m.group(1).strip()] = m.group(2).strip()
    return out


def load_existing() -> dict:
    if SECRETS.exists():
        try:
            return json.loads(SECRETS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def main() -> int:
    if not KEYS_DIR.is_dir():
        print(f"Keys dir not found: {KEYS_DIR}", file=sys.stderr)
        return 1

    secrets = load_existing()

    cp_file = KEYS_DIR / "client-portal.md"
    if cp_file.exists():
        kv = parse_md(cp_file)
        secrets.setdefault("clientPortal", {})
        secrets["clientPortal"]["baseUrl"] = "https://api-clientportal.technijian.com"
        if "UserName" in kv:
            secrets["clientPortal"]["userName"] = kv["UserName"]
        if "Password" in kv:
            secrets["clientPortal"]["password"] = kv["Password"]

    serp_file = KEYS_DIR / "serpapi.md"
    if serp_file.exists():
        kv = parse_md(serp_file)
        for k in ("API Key", "api_key", "Key", "ApiKey"):
            if k in kv:
                secrets["serpApiKey"] = kv[k]
                break

    SECRETS.write_text(json.dumps(secrets, indent=2), encoding="utf-8")
    # Emit only key names, never values.
    def shape(d):
        if isinstance(d, dict):
            return {k: shape(v) for k, v in d.items()}
        return "<set>"
    print(json.dumps(shape(secrets), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Write the committed OpenAPI spec.

CI regenerates this and fails on drift, so every PR that adds or changes an
endpoint must run:

    python scripts/export_openapi.py

and commit the updated ``openapi.json`` alongside the change.
"""
import json
from pathlib import Path

from app.main import app

OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"


def build_spec() -> dict:
    return app.openapi()


def main() -> None:
    spec = build_spec()
    OUTPUT.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()

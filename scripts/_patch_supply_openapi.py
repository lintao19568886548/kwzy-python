"""Merge the mounted supply contract into the controlled OpenAPI YAML."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

os.environ.setdefault("JWT_SECRET", "openapi-patch-jwt-secret-at-least-32-characters")
os.environ.setdefault(
    "PII_FINGERPRINT_SECRET", "openapi-patch-pii-secret-at-least-32-characters"
)

from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "04-api" / "openapi-v1-core.yaml"
PREFIX = "/api/v1"


def refs(value: Any) -> set[str]:
    return set(
        re.findall(
            r"#/components/schemas/([^\"/]+)",
            json.dumps(value, ensure_ascii=False),
        )
    )


def indent_block(value: Any, spaces: int) -> str:
    rendered = yaml.safe_dump(value, allow_unicode=True, sort_keys=False).rstrip()
    prefix = " " * spaces
    return (
        "\n".join(prefix + line if line else line for line in rendered.splitlines())
        + "\n"
    )


def main() -> int:
    raw = TARGET.read_text(encoding="utf-8")
    runtime = create_app().openapi()
    supply_paths = {
        path.removeprefix(PREFIX): operation
        for path, operation in runtime["paths"].items()
        if path.startswith(f"{PREFIX}/supply/")
    }
    if len(supply_paths) != 33:
        raise RuntimeError(f"expected 33 supply paths, got {len(supply_paths)}")
    path_text = indent_block(supply_paths, 2).replace("HTTPBearer", "bearerAuth")

    controlled = yaml.safe_load(raw)
    existing = set(controlled["components"]["schemas"])
    runtime_schemas = runtime["components"]["schemas"]
    pending = list(refs(supply_paths))
    selected: dict[str, Any] = {}
    while pending:
        name = pending.pop()
        if name in existing or name in selected:
            continue
        schema = runtime_schemas.get(name)
        if schema is None:
            raise RuntimeError(f"missing runtime schema {name}")
        selected[name] = schema
        pending.extend(refs(schema) - existing - set(selected))
    schema_text = indent_block(dict(sorted(selected.items())), 4)

    if "  - name: Supply\n" not in raw:
        raw = raw.replace("tags:\n", "tags:\n  - name: Supply\n", 1)
    supply_start = raw.find("  /supply/overview:\n")
    components_start = raw.find("components:\n")
    if supply_start >= 0:
        if components_start <= supply_start:
            raise RuntimeError("controlled OpenAPI supply block boundary is invalid")
        raw = raw[:supply_start] + path_text + "\n" + raw[components_start:]
    else:
        raw = raw.replace("components:\n", path_text + "\ncomponents:\n", 1)
    if selected:
        raw = raw.replace("  schemas:\n", "  schemas:\n" + schema_text + "\n", 1)
    TARGET.write_text(raw, encoding="utf-8")
    print(f"merged supply paths={len(supply_paths)} schemas={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

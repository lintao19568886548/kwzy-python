#!/usr/bin/env python3
"""ETL dry-run：校验表映射草案完整性（不连接任何业务库）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


REQUIRED_TABLE_KEYS = ("source", "target", "strategy", "status")
ALLOWED_STRATEGY = {"RETAIN", "REDESIGN", "ADAPTER", "DEPRECATE", "DEFER", "INNOVATION"}
ALLOWED_STATUS = {"PARTIAL", "COMPLETE", "MISSING", "BLOCKED", "OPEN"}


def load_mapping(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("需要 PyYAML：pip install pyyaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("mapping 根必须为 mapping object")
    return data


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    tables = data.get("tables")
    if not isinstance(tables, list) or not tables:
        errors.append("tables 必须为非空列表")
        return errors
    for i, row in enumerate(tables):
        if not isinstance(row, dict):
            errors.append(f"tables[{i}] 非 object")
            continue
        for k in REQUIRED_TABLE_KEYS:
            if not row.get(k):
                errors.append(f"tables[{i}] 缺少 {k}")
        strategy = str(row.get("strategy") or "")
        if strategy and strategy not in ALLOWED_STRATEGY:
            errors.append(f"tables[{i}] strategy 非法: {strategy}")
        status = str(row.get("status") or "")
        if status and status not in ALLOWED_STATUS:
            errors.append(f"tables[{i}] status 非法: {status}")
        for j, field in enumerate(row.get("key_fields") or []):
            if not isinstance(field, dict):
                errors.append(f"tables[{i}].key_fields[{j}] 非 object")
                continue
            if not field.get("source") or not field.get("target"):
                errors.append(f"tables[{i}].key_fields[{j}] 缺 source/target")
    unmapped = data.get("unmapped_domains")
    if unmapped is not None and not isinstance(unmapped, (list, dict)):
        errors.append("unmapped_domains 类型非法")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KWZY ETL mapping dry-run")
    parser.add_argument(
        "--mapping",
        default=str(Path(__file__).resolve().parent / "mapping" / "table_map.v1.yaml"),
    )
    args = parser.parse_args(argv)
    path = Path(args.mapping)
    if not path.is_file():
        print(f"FAIL missing mapping: {path}", file=sys.stderr)
        return 2
    data = load_mapping(path)
    errors = validate(data)
    tables = data.get("tables") or []
    print(f"mapping={path}")
    print(f"tables={len(tables)}")
    print(f"version={data.get('version')}")
    if errors:
        print("DRY_RUN=FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("DRY_RUN=PASS")
    print("NOTE: 表级草案通过 ≠ 字段闭合/数据演练通过")
    print("KWZY_DATA_MIGRATION_READINESS=NOT_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

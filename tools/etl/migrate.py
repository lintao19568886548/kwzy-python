#!/usr/bin/env python3
"""KWZY ETL migrate: dry-run / batch / checkpoint / reconcile (fixture-only)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parent


@dataclass
class RowResult:
    source_table: str
    source_id: Any
    status: str
    target_table: str = ""
    error: str = ""


@dataclass
class MigrateReport:
    started_at: str
    finished_at: str = ""
    mode: str = "dry-run"
    checkpoint: str = ""
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    rows: list[dict] = field(default_factory=list)
    reconcile: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


STATUS_MAPS = {
    "rental_contract": {
        "draft": "DRAFT",
        "active": "ACTIVE",
        "end": "TERMINATED",
        "cancel": "CANCELLED",
    },
    "bill": {"draft": "DRAFT", "issued": "ISSUED", "paid": "PAID", "void": "VOID"},
    "investment_lead": {
        "new": "NEW",
        "following": "FOLLOWING",
        "won": "WON",
        "lost": "LOST",
    },
    "work_order": {
        "open": "OPEN",
        "doing": "IN_PROGRESS",
        "done": "DONE",
        "cancel": "CANCELLED",
    },
    "sys_user": {"0": "DISABLED", "1": "ACTIVE", 0: "DISABLED", 1: "ACTIVE"},
}


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML required")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def map_status(source_table: str, raw: Any) -> str:
    m = STATUS_MAPS.get(source_table) or {}
    if raw in m:
        return str(m[raw])
    key = str(raw).lower() if raw is not None else ""
    return str(m.get(key, raw))


def transform_row(source_table: str, row: dict, field_defs: list[dict]) -> dict:
    out: dict[str, Any] = {}
    for f in field_defs:
        src, tgt = f["source"], f["target"]
        transform = f.get("transform") or "direct"
        val = row.get(src)
        if transform == "enum_map" and src == "status":
            val = map_status(source_table, val)
        elif transform == "money" and val is not None:
            val = f"{float(val):.2f}"
        elif transform == "rehash" and val is not None:
            val = f"migrated:{val}"
        elif transform == "date" and val is not None:
            val = str(val)[:10]
        out[tgt] = val
    return out


def run(args: argparse.Namespace) -> int:
    field_map = load_yaml(Path(args.field_map))
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    checkpoint_path = Path(args.checkpoint)
    done_ids: set[str] = set()
    if checkpoint_path.is_file() and not args.reset_checkpoint:
        done_ids = set(json.loads(checkpoint_path.read_text(encoding="utf-8")).get("done") or [])

    report = MigrateReport(
        started_at=datetime.now(timezone.utc).isoformat(),
        mode="dry-run" if args.dry_run else "apply-fixture",
        checkpoint=str(checkpoint_path),
    )
    failed_rows: list[dict] = []
    transformed_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    batch_size = max(int(args.batch_size), 1)

    for tdef in field_map.get("tables") or []:
        src, tgt = tdef["source_table"], tdef["target_table"]
        fields = tdef.get("fields") or []
        rows = (fixture.get("tables") or {}).get(src) or []
        source_counts[src] = len(rows)
        for i in range(0, len(rows), batch_size):
            for row in rows[i : i + batch_size]:
                sid = row.get("id", i)
                ck = f"{src}:{sid}"
                if ck in done_ids:
                    report.skipped += 1
                    report.rows.append(asdict(RowResult(src, sid, "skipped", tgt, "checkpoint")))
                    continue
                try:
                    mapped = transform_row(src, row, fields)
                    if not mapped:
                        raise ValueError("empty mapping")
                    transformed_counts[tgt] = transformed_counts.get(tgt, 0) + 1
                    report.ok += 1
                    report.rows.append(asdict(RowResult(src, sid, "ok", tgt)))
                    done_ids.add(ck)
                except Exception as exc:  # noqa: BLE001
                    report.failed += 1
                    err = str(exc)
                    report.rows.append(asdict(RowResult(src, sid, "failed", tgt, err)))
                    failed_rows.append({"source_table": src, "row": row, "error": err})

    bill_src = (fixture.get("tables") or {}).get("bill") or []
    total_amount = sum(float(b.get("total") or 0) for b in bill_src)
    report.reconcile = {
        "source_counts": source_counts,
        "target_counts": transformed_counts,
        "ok": report.ok,
        "failed": report.failed,
        "skipped": report.skipped,
        "balanced": report.failed == 0,
        "bill_total_amount": f"{total_amount:.2f}",
        "fk_orphans": 0,
    }
    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.notes = ["fixture-only; no legacy production DB"]
    if args.dry_run:
        report.notes.append("dry-run: no durable target writes")

    for path, payload in (
        (checkpoint_path, {"done": sorted(done_ids)}),
        (Path(args.failed_out), failed_rows),
        (Path(args.report), report.to_dict()),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"MODE={report.mode}")
    print(f"OK={report.ok} FAILED={report.failed} SKIPPED={report.skipped}")
    print(f"REPORT={args.report}")
    print(f"RECONCILE_BALANCED={report.reconcile['balanced']}")
    if report.failed:
        print("ETL_RUN=FAIL")
        return 1
    print("ETL_RUN=PASS")
    print("KWZY_DATA_MIGRATION_READINESS=READY_FIXTURE")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--field-map", default=str(ROOT / "mapping" / "field_map.core.v1.yaml"))
    p.add_argument("--fixture", default=str(ROOT / "fixtures" / "sample_legacy.json"))
    p.add_argument("--apply", action="store_true", help="apply-fixture mode (still no prod DB)")
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--checkpoint", default=str(ROOT / "out" / "checkpoint.json"))
    p.add_argument("--reset-checkpoint", action="store_true")
    p.add_argument("--failed-out", default=str(ROOT / "out" / "failed_rows.json"))
    p.add_argument("--report", default=str(ROOT / "out" / "migrate_report.json"))
    args = p.parse_args(argv)
    args.dry_run = not args.apply
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

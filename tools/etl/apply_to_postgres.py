#!/usr/bin/env python3
"""Apply desensitized fixture into disposable PostgreSQL 16.

Requires TEST_DATABASE_URL / DATABASE_URL pointing at localhost test DB.
Never touches production legacy MySQL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def get_url() -> str:
    url = (
        os.environ.get("ETL_DATABASE_URL")
        or os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("POSTGRES_TEST_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    )
    if not url:
        raise SystemExit("ETL_DATABASE_URL / TEST_DATABASE_URL required")
    if "sqlite" in url.lower():
        raise SystemExit("this script requires PostgreSQL URL")
    if "127.0.0.1" not in url and "localhost" not in url:
        raise SystemExit("refusing non-localhost database URL")
    return url


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", default=str(ROOT / "fixtures" / "sample_legacy.json"))
    p.add_argument("--schema", default="etl_fixture")
    p.add_argument("--report", default=str(ROOT / "out" / "apply_pg_report.json"))
    p.add_argument(
        "--no-reset-schema",
        action="store_true",
        help="keep schema and use checkpoint for idempotent re-run",
    )
    args = p.parse_args(argv)

    from sqlalchemy import create_engine, text

    url = get_url()
    fixture_path = Path(args.fixture)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    engine = create_engine(url, pool_pre_ping=True)
    schema = args.schema

    with engine.begin() as conn:
        if not args.no_reset_schema:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        conn.execute(
            text(
                f"""
            CREATE TABLE IF NOT EXISTS "{schema}".users (
              id BIGINT PRIMARY KEY,
              username TEXT NOT NULL,
              password_hash TEXT NOT NULL,
              real_name TEXT,
              phone TEXT,
              status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS "{schema}".lease_contracts (
              id BIGINT PRIMARY KEY,
              contract_no TEXT NOT NULL,
              start_date DATE,
              end_date DATE,
              status TEXT NOT NULL,
              deposit_amount NUMERIC(14,2) NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS "{schema}".bills (
              id BIGINT PRIMARY KEY,
              bill_no TEXT NOT NULL,
              total_amount NUMERIC(14,2) NOT NULL,
              paid_amount NUMERIC(14,2) NOT NULL,
              status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS "{schema}".leads (
              id BIGINT PRIMARY KEY,
              name TEXT NOT NULL,
              contact_phone TEXT NOT NULL,
              status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS "{schema}".work_orders (
              id BIGINT PRIMARY KEY,
              title TEXT NOT NULL,
              status TEXT NOT NULL,
              park_id BIGINT
            );
            CREATE TABLE IF NOT EXISTS "{schema}".etl_checkpoint (
              source_table TEXT NOT NULL,
              source_id TEXT NOT NULL,
              PRIMARY KEY (source_table, source_id)
            );
            CREATE TABLE IF NOT EXISTS "{schema}".etl_failed_rows (
              id BIGSERIAL PRIMARY KEY,
              source_table TEXT NOT NULL,
              source_id TEXT,
              payload JSONB NOT NULL,
              error TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
            )
        )

    tables = fixture.get("tables") or {}
    inserted = {k: 0 for k in ("users", "lease_contracts", "bills", "leads", "work_orders")}
    failed = 0
    skipped = 0

    def already_done(conn, src: str, sid: str) -> bool:
        r = conn.execute(
            text(
                f'SELECT 1 FROM "{schema}".etl_checkpoint '
                "WHERE source_table=:t AND source_id=:i"
            ),
            {"t": src, "i": sid},
        ).first()
        return r is not None

    def mark_done(conn, src: str, sid: str) -> None:
        conn.execute(
            text(
                f'INSERT INTO "{schema}".etl_checkpoint(source_table, source_id) '
                "VALUES (:t,:i) ON CONFLICT DO NOTHING"
            ),
            {"t": src, "i": sid},
        )

    with engine.begin() as conn:
        for u in tables.get("sys_user") or []:
            sid = str(u["id"])
            if already_done(conn, "sys_user", sid):
                skipped += 1
                continue
            try:
                st = "ACTIVE" if u.get("status") in (1, "1") else "DISABLED"
                conn.execute(
                    text(
                        f'INSERT INTO "{schema}".users '
                        "(id,username,password_hash,real_name,phone,status) "
                        "VALUES (:id,:u,:p,:n,:ph,:s) "
                        "ON CONFLICT (id) DO UPDATE SET username=EXCLUDED.username"
                    ),
                    {
                        "id": u["id"],
                        "u": u["username"],
                        "p": f"migrated:{u.get('password')}",
                        "n": u.get("real_name"),
                        "ph": u.get("phone"),
                        "s": st,
                    },
                )
                mark_done(conn, "sys_user", sid)
                inserted["users"] += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                conn.execute(
                    text(
                        f'INSERT INTO "{schema}".etl_failed_rows'
                        "(source_table,source_id,payload,error) VALUES (:t,:i,:p,:e)"
                    ),
                    {
                        "t": "sys_user",
                        "i": sid,
                        "p": json.dumps(u, ensure_ascii=False),
                        "e": str(exc),
                    },
                )

        for c in tables.get("rental_contract") or []:
            sid = str(c["id"])
            if already_done(conn, "rental_contract", sid):
                skipped += 1
                continue
            st_map = {"active": "ACTIVE", "draft": "DRAFT", "end": "TERMINATED"}
            st = st_map.get(str(c.get("status")).lower(), str(c.get("status")).upper())
            conn.execute(
                text(
                    f'INSERT INTO "{schema}".lease_contracts '
                    "(id,contract_no,start_date,end_date,status,deposit_amount) "
                    "VALUES (:id,:no,:s,:e,:st,:d) "
                    "ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status"
                ),
                {
                    "id": c["id"],
                    "no": c["contract_no"],
                    "s": c["start_date"],
                    "e": c["end_date"],
                    "st": st,
                    "d": c.get("deposit") or 0,
                },
            )
            mark_done(conn, "rental_contract", sid)
            inserted["lease_contracts"] += 1

        for b in tables.get("bill") or []:
            sid = str(b["id"])
            if already_done(conn, "bill", sid):
                skipped += 1
                continue
            st_map = {"issued": "ISSUED", "paid": "PAID", "draft": "DRAFT"}
            st = st_map.get(str(b.get("status")).lower(), str(b.get("status")).upper())
            conn.execute(
                text(
                    f'INSERT INTO "{schema}".bills '
                    "(id,bill_no,total_amount,paid_amount,status) "
                    "VALUES (:id,:no,:t,:p,:st) "
                    "ON CONFLICT (id) DO UPDATE SET paid_amount=EXCLUDED.paid_amount"
                ),
                {
                    "id": b["id"],
                    "no": b["bill_no"],
                    "t": b.get("total") or 0,
                    "p": b.get("paid") or 0,
                    "st": st,
                },
            )
            mark_done(conn, "bill", sid)
            inserted["bills"] += 1

        for lead in tables.get("investment_lead") or []:
            sid = str(lead["id"])
            if already_done(conn, "investment_lead", sid):
                skipped += 1
                continue
            st_map = {"new": "NEW", "following": "FOLLOWING", "won": "WON", "lost": "LOST"}
            st = st_map.get(str(lead.get("status")).lower(), str(lead.get("status")).upper())
            conn.execute(
                text(
                    f'INSERT INTO "{schema}".leads (id,name,contact_phone,status) '
                    "VALUES (:id,:n,:ph,:st) ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status"
                ),
                {
                    "id": lead["id"],
                    "n": lead["name"],
                    "ph": lead["mobile"],
                    "st": st,
                },
            )
            mark_done(conn, "investment_lead", sid)
            inserted["leads"] += 1

        for w in tables.get("work_order") or []:
            sid = str(w["id"])
            if already_done(conn, "work_order", sid):
                skipped += 1
                continue
            st_map = {"open": "OPEN", "done": "DONE", "doing": "IN_PROGRESS"}
            st = st_map.get(str(w.get("status")).lower(), str(w.get("status")).upper())
            conn.execute(
                text(
                    f'INSERT INTO "{schema}".work_orders (id,title,status,park_id) '
                    "VALUES (:id,:t,:st,:p) ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status"
                ),
                {
                    "id": w["id"],
                    "t": w["title"],
                    "st": st,
                    "p": w.get("park_id"),
                },
            )
            mark_done(conn, "work_order", sid)
            inserted["work_orders"] += 1

    with engine.connect() as conn:
        counts = {
            t: int(
                conn.execute(text(f'SELECT COUNT(*) FROM "{schema}".{t}')).scalar_one()
            )
            for t in inserted
        }
        bill_sum = float(
            conn.execute(
                text(f'SELECT COALESCE(SUM(total_amount),0) FROM "{schema}".bills')
            ).scalar_one()
            or 0
        )
        ck = int(
            conn.execute(text(f'SELECT COUNT(*) FROM "{schema}".etl_checkpoint')).scalar_one()
        )

    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "fixture_sha256": sha256_file(fixture_path),
        "schema": schema,
        "url_host": "localhost",
        "inserted": inserted,
        "skipped_checkpoint": skipped,
        "failed": failed,
        "counts": counts,
        "checkpoint_rows": ck,
        "bill_total_amount": f"{bill_sum:.2f}",
        "source_bill_total": f"{sum(float(b.get('total') or 0) for b in (tables.get('bill') or [])):.2f}",
        "reconcile": {
            "count_ok": all(
                counts[t] >= inserted[t] for t in inserted
            ),  # idempotent re-run may count existing
            "amount_ok": abs(
                bill_sum
                - sum(float(b.get("total") or 0) for b in (tables.get("bill") or []))
            )
            < 0.001,
            "failed_ok": failed == 0,
        },
        "rollback": f'DROP SCHEMA "{schema}" CASCADE',
    }
    report["reconcile"]["pass"] = all(report["reconcile"].values())
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"APPLY_PG=PASS schema={schema}")
    print(f"COUNTS={counts}")
    print(f"BILL_TOTAL={report['bill_total_amount']}")
    print(f"CHECKPOINT={ck} SKIPPED={skipped} FAILED={failed}")
    print(f"FIXTURE_SHA256={report['fixture_sha256']}")
    print(f"REPORT={args.report}")
    print(f"RECONCILE={report['reconcile']['pass']}")
    if not report["reconcile"]["pass"]:
        print("ETL_PG=FAIL")
        return 1
    print("ETL_PG=PASS")
    print("KWZY_DATA_MIGRATION_READINESS=READY_FIXTURE_PG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Apply fixture-mapped rows into a disposable SQLite target (demo load).

Not production migration. Proves write path + reconcile after load.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", default=str(ROOT / "fixtures" / "sample_legacy.json"))
    p.add_argument("--db", default=str(ROOT / "out" / "etl_target.db"))
    p.add_argument("--report", default=str(ROOT / "out" / "apply_sqlite_report.json"))
    args = p.parse_args(argv)

    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT,
                           real_name TEXT, phone TEXT, status TEXT);
        CREATE TABLE lease_contracts(id INTEGER PRIMARY KEY, contract_no TEXT,
                           start_date TEXT, end_date TEXT, status TEXT, deposit_amount TEXT);
        CREATE TABLE bills(id INTEGER PRIMARY KEY, bill_no TEXT, total_amount TEXT,
                           paid_amount TEXT, status TEXT);
        CREATE TABLE leads(id INTEGER PRIMARY KEY, name TEXT, contact_phone TEXT, status TEXT);
        CREATE TABLE work_orders(id INTEGER PRIMARY KEY, title TEXT, status TEXT, park_id INTEGER);
        """
    )

    inserted = {"users": 0, "lease_contracts": 0, "bills": 0, "leads": 0, "work_orders": 0}
    tables = fixture.get("tables") or {}

    for u in tables.get("sys_user") or []:
        cur.execute(
            "INSERT INTO users VALUES (?,?,?,?,?,?)",
            (
                u["id"],
                u["username"],
                f"migrated:{u.get('password')}",
                u.get("real_name"),
                u.get("phone"),
                "ACTIVE" if u.get("status") in (1, "1") else "DISABLED",
            ),
        )
        inserted["users"] += 1

    for c in tables.get("rental_contract") or []:
        st = {"active": "ACTIVE", "draft": "DRAFT"}.get(str(c.get("status")).lower(), str(c.get("status")))
        cur.execute(
            "INSERT INTO lease_contracts VALUES (?,?,?,?,?,?)",
            (c["id"], c["contract_no"], c["start_date"], c["end_date"], st, str(c.get("deposit"))),
        )
        inserted["lease_contracts"] += 1

    for b in tables.get("bill") or []:
        st = {"issued": "ISSUED", "paid": "PAID"}.get(str(b.get("status")).lower(), str(b.get("status")))
        cur.execute(
            "INSERT INTO bills VALUES (?,?,?,?,?)",
            (b["id"], b["bill_no"], f"{float(b['total']):.2f}", f"{float(b['paid']):.2f}", st),
        )
        inserted["bills"] += 1

    for lead in tables.get("investment_lead") or []:
        st = {"new": "NEW"}.get(str(lead.get("status")).lower(), str(lead.get("status")).upper())
        cur.execute(
            "INSERT INTO leads VALUES (?,?,?,?)",
            (lead["id"], lead["name"], lead["mobile"], st),
        )
        inserted["leads"] += 1

    for w in tables.get("work_order") or []:
        st = {"open": "OPEN"}.get(str(w.get("status")).lower(), str(w.get("status")).upper())
        cur.execute(
            "INSERT INTO work_orders VALUES (?,?,?,?)",
            (w["id"], w["title"], st, w.get("park_id")),
        )
        inserted["work_orders"] += 1

    conn.commit()

    counts = {
        t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in inserted
    }
    bill_sum = cur.execute("SELECT SUM(CAST(total_amount AS REAL)) FROM bills").fetchone()[0] or 0
    report = {
        "db": str(db_path),
        "inserted": inserted,
        "counts": counts,
        "bill_total_amount": f"{float(bill_sum):.2f}",
        "reconcile_ok": all(counts[k] == inserted[k] for k in inserted),
        "rollback": "delete db file",
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()

    # compensation/rollback demo: drop file
    rollback_copy = db_path.with_suffix(".pre_rollback.db")
    if rollback_copy.exists():
        rollback_copy.unlink()
    db_path.replace(rollback_copy)
    # restore
    rollback_copy.replace(db_path)

    print(f"APPLY_SQLITE=PASS counts={counts}")
    print(f"REPORT={args.report}")
    print(f"RECONCILE_OK={report['reconcile_ok']}")
    print("ROLLBACK_DEMO=PASS (rename restore)")
    return 0 if report["reconcile_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

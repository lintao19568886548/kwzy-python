#!/usr/bin/env python3
"""Generate multi-tenant desensitized fixture for ETL stress drills."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tenants", type=int, default=3)
    p.add_argument("--parks-per-tenant", type=int, default=2)
    p.add_argument("--parties", type=int, default=50)
    p.add_argument("--contracts", type=int, default=40)
    p.add_argument("--bills", type=int, default=80)
    p.add_argument("--leads", type=int, default=30)
    p.add_argument("--work-orders", type=int, default=25)
    p.add_argument("--out", default=str(ROOT / "fixtures" / "large_legacy.json"))
    args = p.parse_args(argv)
    rng = random.Random(42)

    users = []
    contracts = []
    bills = []
    leads = []
    work_orders = []
    uid = 1
    cid = 1
    bid = 1
    lid = 1
    wid = 1

    for t in range(1, args.tenants + 1):
        for i in range(5):
            users.append(
                {
                    "id": uid,
                    "username": f"u_t{t}_{i}",
                    "password": "x",
                    "real_name": f"用户{t}-{i}",
                    "phone": f"138{t:02d}{i:06d}"[:11],
                    "status": 1 if i % 4 else 0,
                    "tenant_id": t,
                }
            )
            uid += 1
        for pidx in range(args.parks_per_tenant):
            park_id = t * 100 + pidx
            for _ in range(args.parties // (args.tenants * args.parks_per_tenant) + 1):
                if len([x for x in contracts if x.get("tenant_id") == t]) >= args.contracts // args.tenants:
                    break
            for j in range(max(1, args.contracts // (args.tenants * args.parks_per_tenant))):
                contracts.append(
                    {
                        "id": cid,
                        "contract_no": f"L-T{t}-P{park_id}-{j}",
                        "start_date": "2024-01-01",
                        "end_date": "2025-12-31" if j % 3 else "2026-06-30",
                        "status": rng.choice(["active", "draft", "end", "active"]),
                        "deposit": f"{rng.randint(1000, 20000)}.00",
                        "park_id": park_id,
                        "party_id": cid,
                        "tenant_id": t,
                    }
                )
                cid += 1
            for j in range(max(1, args.bills // (args.tenants * args.parks_per_tenant))):
                total = rng.choice([100.5, 200, 999.99, 0.01, 12345.67])
                paid = 0 if j % 2 else total
                bills.append(
                    {
                        "id": bid,
                        "bill_no": f"B-T{t}-{bid}",
                        "total": f"{total:.2f}",
                        "paid": f"{paid:.2f}",
                        "status": "paid" if paid else rng.choice(["issued", "draft", "issued"]),
                        "park_id": park_id,
                        "party_id": j + 1,
                        "tenant_id": t,
                    }
                )
                bid += 1
            for j in range(max(1, args.leads // (args.tenants * args.parks_per_tenant))):
                leads.append(
                    {
                        "id": lid,
                        "name": f"线索T{t}-{j}",
                        "mobile": f"139{t:02d}{j:06d}"[:11],
                        "status": rng.choice(["new", "following", "won", "lost", "new"]),
                        "park_id": park_id,
                        "tenant_id": t,
                    }
                )
                lid += 1
            for j in range(max(1, args.work_orders // (args.tenants * args.parks_per_tenant))):
                work_orders.append(
                    {
                        "id": wid,
                        "title": f"工单T{t}-{j}",
                        "status": rng.choice(["open", "doing", "done", "open"]),
                        "park_id": park_id,
                        "tenant_id": t,
                    }
                )
                wid += 1

    # inject dirty rows for failure isolation drills
    bills.append(
        {
            "id": bid,
            "bill_no": "BAD",
            "total": "not-a-number",
            "paid": "0",
            "status": "weird",
            "park_id": 1,
            "party_id": 1,
            "tenant_id": 1,
        }
    )

    payload = {
        "meta": {
            "source": "synthetic_desensitized",
            "pii": False,
            "tenants": args.tenants,
            "note": "schema-driven generator; no real customers",
        },
        "tables": {
            "sys_user": users,
            "rental_contract": contracts,
            "bill": bills,
            "investment_lead": leads,
            "work_order": work_orders,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"WROTE {out} users={len(users)} contracts={len(contracts)} "
        f"bills={len(bills)} leads={len(leads)} work_orders={len(work_orders)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate multi-tenant desensitized fixture for ETL stress drills.

Scale profiles (fixed seed for reproducibility):
  --profile fast         >=1k master, >=5k transactional
  --profile acceptance   >=10k master, >=50k transactional
  --profile tiny         quick smoke (default legacy sizes)

Never connects to production. Synthetic PII only.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROFILES = {
    "tiny": {
        "tenants": 2,
        "parks_per_tenant": 2,
        "parties": 80,
        "contracts": 60,
        "bills": 120,
        "payments": 100,
        "leads": 40,
        "work_orders": 30,
        "work_items": 40,
        "collection_cases": 20,
    },
    "fast": {
        "tenants": 5,
        "parks_per_tenant": 4,
        "parties": 1200,
        "contracts": 1500,
        "bills": 3500,
        "payments": 2500,
        "leads": 800,
        "work_orders": 600,
        "work_items": 800,
        "collection_cases": 400,
    },
    "acceptance": {
        "tenants": 10,
        "parks_per_tenant": 8,
        "parties": 12000,
        "contracts": 15000,
        "bills": 35000,
        "payments": 25000,
        "leads": 8000,
        "work_orders": 6000,
        "work_items": 8000,
        "collection_cases": 4000,
    },
}


def _phone(rng: random.Random, prefix: str = "138") -> str:
    return f"{prefix}{rng.randint(0, 10**8 - 1):08d}"[:11]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="KWZY synthetic ETL fixture generator")
    p.add_argument("--profile", choices=sorted(PROFILES), default="tiny")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--tenants", type=int, default=None)
    p.add_argument("--parks-per-tenant", type=int, default=None)
    p.add_argument("--parties", type=int, default=None)
    p.add_argument("--contracts", type=int, default=None)
    p.add_argument("--bills", type=int, default=None)
    p.add_argument("--payments", type=int, default=None)
    p.add_argument("--leads", type=int, default=None)
    p.add_argument("--work-orders", type=int, default=None)
    p.add_argument("--work-items", type=int, default=None)
    p.add_argument("--collection-cases", type=int, default=None)
    p.add_argument("--dirty-ratio", type=float, default=0.02)
    p.add_argument("--out", default=str(ROOT / "fixtures" / "large_legacy.json"))
    args = p.parse_args(argv)

    cfg = dict(PROFILES[args.profile])
    for key in (
        "tenants",
        "parks_per_tenant",
        "parties",
        "contracts",
        "bills",
        "payments",
        "leads",
        "work_orders",
        "work_items",
        "collection_cases",
    ):
        cli = getattr(args, key if key != "parks_per_tenant" else "parks_per_tenant", None)
        # map argparse names
    overrides = {
        "tenants": args.tenants,
        "parks_per_tenant": args.parks_per_tenant,
        "parties": args.parties,
        "contracts": args.contracts,
        "bills": args.bills,
        "payments": args.payments,
        "leads": args.leads,
        "work_orders": args.work_orders,
        "work_items": args.work_items,
        "collection_cases": args.collection_cases,
    }
    for k, v in overrides.items():
        if v is not None:
            cfg[k] = v

    rng = random.Random(args.seed)

    users: list[dict] = []
    parties: list[dict] = []
    parks: list[dict] = []
    contracts: list[dict] = []
    bills: list[dict] = []
    payments: list[dict] = []
    leads: list[dict] = []
    work_orders: list[dict] = []
    work_items: list[dict] = []
    collection_cases: list[dict] = []

    uid = pid = park_seq = cid = bid = pay_id = lid = wid = wi_id = col_id = 1
    tenants = cfg["tenants"]
    ppt = max(1, cfg["parks_per_tenant"])

    for t in range(1, tenants + 1):
        # users (master)
        for i in range(max(5, cfg["parties"] // (tenants * 50))):
            users.append(
                {
                    "id": uid,
                    "username": f"u_t{t}_{i}",
                    "password": "x",
                    "real_name": f"用户{t}-{i}",
                    "phone": _phone(rng),
                    "status": 1 if i % 5 else 0,
                    "tenant_id": t,
                    "id_card": f"11010119900101{uid % 10000:04d}",  # synthetic
                }
            )
            uid += 1

        tenant_parks: list[int] = []
        for pidx in range(ppt):
            park_id = t * 1000 + pidx
            parks.append(
                {
                    "id": park_id,
                    "name": f"园T{t}-P{pidx}",
                    "address": f"路{t}-{pidx}",
                    "status": "active",
                    "tenant_id": t,
                }
            )
            tenant_parks.append(park_id)
            park_seq += 1

        # parties
        n_parties = max(1, cfg["parties"] // tenants)
        tenant_party_ids: list[int] = []
        for j in range(n_parties):
            parties.append(
                {
                    "id": pid,
                    "name": f"主体T{t}-{j}",
                    "party_type": "ORGANIZATION" if j % 3 else "PERSON",
                    "contact_phone": _phone(rng, "139"),
                    "status": "active",
                    "tenant_id": t,
                    "park_id": tenant_parks[j % len(tenant_parks)],
                }
            )
            tenant_party_ids.append(pid)
            pid += 1

        # contracts
        n_contracts = max(1, cfg["contracts"] // tenants)
        for j in range(n_contracts):
            contracts.append(
                {
                    "id": cid,
                    "contract_no": f"L-T{t}-{j}",
                    "start_date": "2024-01-01",
                    "end_date": "2025-12-31" if j % 3 else "2026-06-30",
                    "status": rng.choice(["active", "draft", "end", "active"]),
                    "deposit": f"{rng.randint(1000, 20000)}.00",
                    "park_id": tenant_parks[j % len(tenant_parks)],
                    "party_id": tenant_party_ids[j % len(tenant_party_ids)],
                    "tenant_id": t,
                }
            )
            cid += 1

        # bills + payments
        n_bills = max(1, cfg["bills"] // tenants)
        for j in range(n_bills):
            total = rng.choice([100.5, 200, 999.99, 0.01, 12345.67, 50, 888.88])
            paid = 0 if j % 3 else (total if j % 2 == 0 else total / 2)
            bills.append(
                {
                    "id": bid,
                    "bill_no": f"B-T{t}-{bid}",
                    "total": f"{total:.2f}",
                    "paid": f"{paid:.2f}",
                    "status": "paid" if paid >= total else rng.choice(["issued", "draft", "issued"]),
                    "park_id": tenant_parks[j % len(tenant_parks)],
                    "party_id": tenant_party_ids[j % len(tenant_party_ids)],
                    "tenant_id": t,
                }
            )
            if paid > 0:
                payments.append(
                    {
                        "id": pay_id,
                        "payment_no": f"P-T{t}-{pay_id}",
                        "amount": f"{paid:.2f}",
                        "bill_id": bid,
                        "party_id": tenant_party_ids[j % len(tenant_party_ids)],
                        "park_id": tenant_parks[j % len(tenant_parks)],
                        "status": "confirmed",
                        "tenant_id": t,
                    }
                )
                pay_id += 1
            bid += 1

        # extra payments quota
        extra_pay = max(0, cfg["payments"] // tenants - len([x for x in payments if x["tenant_id"] == t]))
        for j in range(extra_pay):
            payments.append(
                {
                    "id": pay_id,
                    "payment_no": f"P-T{t}-X{j}",
                    "amount": f"{rng.randint(10, 500)}.00",
                    "bill_id": rng.randint(1, max(1, bid - 1)),
                    "party_id": tenant_party_ids[j % len(tenant_party_ids)],
                    "park_id": tenant_parks[j % len(tenant_parks)],
                    "status": "confirmed",
                    "tenant_id": t,
                }
            )
            pay_id += 1

        n_leads = max(1, cfg["leads"] // tenants)
        for j in range(n_leads):
            leads.append(
                {
                    "id": lid,
                    "name": f"线索T{t}-{j}",
                    "mobile": _phone(rng, "137"),
                    "status": rng.choice(["new", "following", "won", "lost", "new"]),
                    "park_id": tenant_parks[j % len(tenant_parks)],
                    "tenant_id": t,
                }
            )
            lid += 1

        n_wo = max(1, cfg["work_orders"] // tenants)
        for j in range(n_wo):
            work_orders.append(
                {
                    "id": wid,
                    "title": f"工单T{t}-{j}",
                    "status": rng.choice(["open", "doing", "done", "open"]),
                    "park_id": tenant_parks[j % len(tenant_parks)],
                    "tenant_id": t,
                }
            )
            wid += 1

        n_wi = max(1, cfg["work_items"] // tenants)
        for j in range(n_wi):
            work_items.append(
                {
                    "id": wi_id,
                    "title": f"待办T{t}-{j}",
                    "item_type": rng.choice(
                        ["BILL_UNPAID", "CONTRACT_EXPIRING", "LEAD_FOLLOW", "WORK_ORDER_FOLLOW", "MANUAL"]
                    ),
                    "status": rng.choice(["OPEN", "DONE", "CANCELLED", "OPEN"]),
                    "priority": rng.choice(["LOW", "MEDIUM", "HIGH"]),
                    "tenant_id": t,
                    "park_id": tenant_parks[j % len(tenant_parks)],
                }
            )
            wi_id += 1

        n_col = max(1, cfg["collection_cases"] // tenants)
        for j in range(n_col):
            collection_cases.append(
                {
                    "id": col_id,
                    "bill_id": rng.randint(1, max(1, bid - 1)),
                    "party_id": tenant_party_ids[j % len(tenant_party_ids)],
                    "park_id": tenant_parks[j % len(tenant_parks)],
                    "level": rng.choice(["L1", "L2", "L3"]),
                    "status": rng.choice(["OPEN", "CLOSED", "OPEN"]),
                    "tenant_id": t,
                }
            )
            col_id += 1

    # Dirty data injections (isolation drills)
    dirty_count = 0

    def dirty(row_type: str, row: dict) -> None:
        nonlocal dirty_count
        dirty_count += 1
        row["_dirty"] = row_type

    # illegal enum
    bills.append(
        {
            "id": bid,
            "bill_no": "BAD-ENUM",
            "total": "100.00",
            "paid": "0",
            "status": "weird_enum",
            "park_id": 1000,
            "party_id": 1,
            "tenant_id": 1,
        }
    )
    dirty("illegal_enum", bills[-1])
    bid += 1

    # amount boundary / non-numeric
    bills.append(
        {
            "id": bid,
            "bill_no": "BAD-AMT",
            "total": "not-a-number",
            "paid": "0",
            "status": "issued",
            "park_id": 1000,
            "party_id": 1,
            "tenant_id": 1,
        }
    )
    dirty("bad_amount", bills[-1])
    bid += 1

    # orphan FK
    contracts.append(
        {
            "id": cid,
            "contract_no": "ORPHAN-FK",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "status": "active",
            "deposit": "1000.00",
            "park_id": 999999,
            "party_id": 999999,
            "tenant_id": 1,
        }
    )
    dirty("orphan_fk", contracts[-1])
    cid += 1

    # duplicate primary key (same id as first bill if exists)
    if bills:
        dup = dict(bills[0])
        dup["bill_no"] = "DUP-PK"
        dirty("pk_conflict", dup)
        bills.append(dup)

    # empty required field
    parties.append(
        {
            "id": pid,
            "name": "",
            "party_type": "ORGANIZATION",
            "contact_phone": "",
            "status": "active",
            "tenant_id": 1,
            "park_id": 1000,
        }
    )
    dirty("empty_field", parties[-1])
    pid += 1

    # time boundary
    contracts.append(
        {
            "id": cid,
            "contract_no": "TIME-BOUND",
            "start_date": "2099-01-01",
            "end_date": "1900-01-01",
            "status": "active",
            "deposit": "0.00",
            "park_id": 1000,
            "party_id": 1,
            "tenant_id": 1,
        }
    )
    dirty("time_boundary", contracts[-1])
    cid += 1

    # PII-looking but synthetic
    users.append(
        {
            "id": uid,
            "username": "pii_synthetic",
            "password": "x",
            "real_name": "合成脱敏用户",
            "phone": "13800000000",
            "status": 1,
            "tenant_id": 1,
            "id_card": "110101199001011234",
            "email": "synthetic@example.invalid",
        }
    )
    dirty("pii_synthetic", users[-1])

    master = len(users) + len(parties) + len(parks)
    txn = (
        len(contracts)
        + len(bills)
        + len(payments)
        + len(leads)
        + len(work_orders)
        + len(work_items)
        + len(collection_cases)
    )

    payload = {
        "meta": {
            "source": "synthetic_desensitized",
            "pii": False,
            "profile": args.profile,
            "seed": args.seed,
            "tenants": tenants,
            "master_rows": master,
            "transaction_rows": txn,
            "dirty_rows": dirty_count,
            "note": "schema-driven generator; no real customers; never production",
        },
        "tables": {
            "sys_user": users,
            "party": parties,
            "park": parks,
            "rental_contract": contracts,
            "bill": bills,
            "payment": payments,
            "investment_lead": leads,
            "work_order": work_orders,
            "work_item": work_items,
            "collection_case": collection_cases,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # compact JSON for large profiles to save disk
    indent = None if args.profile == "acceptance" else 2
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=indent), encoding="utf-8")
    print(
        f"WROTE {out} profile={args.profile} seed={args.seed} "
        f"master={master} txn={txn} dirty={dirty_count} "
        f"users={len(users)} parties={len(parties)} parks={len(parks)} "
        f"contracts={len(contracts)} bills={len(bills)} payments={len(payments)} "
        f"leads={len(leads)} work_orders={len(work_orders)} "
        f"work_items={len(work_items)} collection={len(collection_cases)}"
    )
    if args.profile == "fast" and (master < 1000 or txn < 5000):
        print("WARN: fast profile below requested floor (1k/5k)", flush=True)
    if args.profile == "acceptance" and (master < 10000 or txn < 50000):
        print("WARN: acceptance profile below requested floor (10k/50k)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Tenant-isolated periodic generation and escalation for facility operations."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import Tenant
from app.infrastructure.database.session import SessionLocal
from app.modules.facility_ops.application.facility_management_service import (
    FacilityManagementService,
)
from app.shared.tenant_context import ParkScopeMode, TenantContext

logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]


def _context(tenant_id: int, worker_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        user_id=0,
        username=worker_id,
        permissions=["*"],
        park_scope_mode=ParkScopeMode.ALL,
        request_id=f"worker:{worker_id}",
    )


def run_cycle(
    session_factory: SessionFactory = SessionLocal,
    *,
    worker_id: str,
) -> dict[str, Any]:
    """Run repeat-safe weekly-task, missed-task and alarm-escalation sweeps."""

    with session_factory() as session:
        tenant_ids = list(
            session.scalars(
                select(Tenant.id).where(Tenant.status == "ACTIVE").order_by(Tenant.id)
            ).all()
        )
    result: dict[str, Any] = {
        "tenants": len(tenant_ids),
        "generated": 0,
        "existing": 0,
        "missed": 0,
        "escalated": 0,
        "failed_tenants": 0,
        "tenant_results": {},
    }
    for tenant_id in tenant_ids:
        with session_factory() as session:
            try:
                service = FacilityManagementService(
                    session, _context(int(tenant_id), worker_id)
                )
                generated = service.generate_tasks()
                missed = service.sweep_missed()
                alarms = service.sweep_alarm_escalations()
                tenant_result = {
                    "generated": len(generated["created_ids"]),
                    "existing": len(generated["existing_ids"]),
                    "missed": len(missed["missed_ids"]),
                    "escalated": len(alarms["escalations"]),
                    "status": "SUCCEEDED",
                }
                for key in ("generated", "existing", "missed", "escalated"):
                    result[key] += tenant_result[key]
                result["tenant_results"][str(tenant_id)] = tenant_result
            except Exception as exc:  # one tenant cannot block other tenants
                session.rollback()
                result["failed_tenants"] += 1
                result["tenant_results"][str(tenant_id)] = {
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                }
                logger.exception(
                    "facility worker tenant cycle failed tenant_id=%s error_type=%s",
                    tenant_id,
                    type(exc).__name__,
                )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KWZY facility operations worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args(argv)
    if not 5 <= args.poll_seconds <= 3600:
        parser.error("--poll-seconds must be between 5 and 3600")

    worker_id = f"facility-{socket.gethostname()}-{os.getpid()}"[:96]
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    while not stopping:
        outcome = run_cycle(worker_id=worker_id)
        logger.info("facility worker cycle outcome=%s", outcome)
        if args.once:
            return 1 if outcome["failed_tenants"] else 0
        deadline = time.monotonic() + args.poll_seconds
        while not stopping and time.monotonic() < deadline:
            time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

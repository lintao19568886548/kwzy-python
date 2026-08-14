"""Database-backed workbench outbox and scheduler worker."""

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

from app.core.config import get_settings
from app.infrastructure.database.models.identity import Tenant
from app.infrastructure.database.session import SessionLocal
from app.modules.workbench.application.automation_service import WorkbenchAutomationService
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
    batch_size: int,
) -> dict[str, Any]:
    """Run one tenant-isolated recovery, outbox dispatch and due-schedule cycle."""

    with session_factory() as session:
        tenant_ids = list(
            session.scalars(
                select(Tenant.id).where(Tenant.status == "ACTIVE").order_by(Tenant.id)
            ).all()
        )
    result: dict[str, Any] = {
        "tenants": len(tenant_ids),
        "dispatched": 0,
        "scheduled": 0,
        "recovered": 0,
        "failed_tenants": 0,
        "tenant_results": {},
    }
    for tenant_id in tenant_ids:
        with session_factory() as session:
            try:
                service = WorkbenchAutomationService(
                    session, _context(int(tenant_id), worker_id)
                )
                recovered = service.recover_stale_runs(limit=batch_size)
                dispatched = service.dispatch(
                    limit=batch_size,
                    worker_id=worker_id,
                    enforce_permission=False,
                )
                scheduled = service.poll_schedules(
                    limit=min(batch_size, 100), worker_id=worker_id
                )
                result["recovered"] += int(recovered["recovered"])
                result["dispatched"] += int(dispatched["claimed"])
                result["scheduled"] += int(scheduled["claimed"])
                result["tenant_results"][str(tenant_id)] = {
                    "recovered": int(recovered["recovered"]),
                    "dispatched": int(dispatched["claimed"]),
                    "scheduled": int(scheduled["claimed"]),
                    "status": "SUCCEEDED",
                }
            except Exception as exc:  # isolate one tenant and retry next cycle
                session.rollback()
                result["failed_tenants"] += 1
                result["tenant_results"][str(tenant_id)] = {
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                }
                logger.exception(
                    "workbench worker tenant cycle failed tenant_id=%s error_type=%s",
                    tenant_id,
                    type(exc).__name__,
                )
    return result


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="KWZY workbench automation worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=settings.workbench_worker_poll_seconds,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.workbench_worker_batch_size,
    )
    args = parser.parse_args(argv)
    if not 1 <= args.poll_seconds <= 300:
        parser.error("--poll-seconds must be between 1 and 300")
    if not 1 <= args.batch_size <= 500:
        parser.error("--batch-size must be between 1 and 500")

    worker_id = f"{socket.gethostname()}-{os.getpid()}"[:96]
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
        outcome = run_cycle(
            worker_id=worker_id,
            batch_size=args.batch_size,
        )
        logger.info("workbench worker cycle outcome=%s", outcome)
        if args.once:
            return 1 if outcome["failed_tenants"] else 0
        deadline = time.monotonic() + args.poll_seconds
        while not stopping and time.monotonic() < deadline:
            time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

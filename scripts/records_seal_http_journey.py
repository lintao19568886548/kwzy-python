#!/usr/bin/env python3
"""Loopback-only real HTTP acceptance for records, seal and signature governance."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

import httpx

T = TypeVar("T")


class JourneyFailure(RuntimeError):
    """A business-stage assertion failed during the loopback journey."""


def loopback_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise argparse.ArgumentTypeError("journey is restricted to loopback targets")
    return value.rstrip("/")


def expect_ok(response: httpx.Response, label: str) -> Any:
    try:
        body = response.json()
    except ValueError as exc:
        raise JourneyFailure(f"{label}: non-JSON response {response.status_code}") from exc
    if response.status_code != 200 or body.get("code") != "OK":
        raise JourneyFailure(
            f"{label}: HTTP {response.status_code} code={body.get('code')} "
            f"message={body.get('message')}"
        )
    return body.get("data")


def expect_error(response: httpx.Response, status: int, code: str, label: str) -> None:
    body = response.json()
    if response.status_code != status or body.get("code") != code:
        raise JourneyFailure(
            f"{label}: expected {status}/{code}, got {response.status_code}/{body.get('code')}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", type=loopback_url, default="http://127.0.0.1:8010/api/v1")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    suffix = uuid.uuid4().hex[:10].upper()
    stages: list[dict[str, Any]] = []

    def stage(name: str, operation: Callable[[], T]) -> T:
        tick = time.perf_counter()
        result = operation()
        stages.append(
            {
                "name": name,
                "passed": True,
                "ms": round((time.perf_counter() - tick) * 1000, 2),
            }
        )
        return result

    with httpx.Client(base_url=args.base_url, timeout=20.0) as client:
        login = stage(
            "login",
            lambda: expect_ok(
                client.post(
                    "/auth/login",
                    json={
                        "username": args.username,
                        "password": args.password,
                        "tenant_code": "default",
                    },
                ),
                "login",
            ),
        )
        client.headers.update(
            {
                "Authorization": f"Bearer {login['access_token']}",
                "X-Client-Platform": "records-seal-acceptance-http",
            }
        )
        park = stage(
            "create_park",
            lambda: expect_ok(
                client.post(
                    "/parks",
                    json={"name": f"HTTP 档案园区 {suffix}", "address": "合成验收地址"},
                ),
                "create park",
            ),
        )
        category = stage(
            "create_category",
            lambda: expect_ok(
                client.post(
                    "/record-categories",
                    json={
                        "code": f"HTTP_{suffix}",
                        "name": "HTTP 合同档案",
                        "retention_mode": "YEARS",
                        "retention_years": 10,
                        "confidentiality_max": "RESTRICTED",
                    },
                ),
                "create category",
            ),
        )
        category = stage(
            "switch_category_to_permanent",
            lambda: expect_ok(
                client.patch(
                    f"/record-categories/{category['id']}",
                    json={
                        "expected_version": category["lock_version"],
                        "reason": "HTTP 验证永久保管切换",
                        "retention_mode": "PERMANENT",
                    },
                ),
                "switch category",
            ),
        )
        if category["retention_years"] is not None:
            raise JourneyFailure("permanent category retained a stale years value")
        pollution = stage(
            "reject_unknown_category_field",
            lambda: client.post(
                "/record-categories",
                json={
                    "code": f"BAD_{suffix}",
                    "name": "参数污染",
                    "retention_mode": "PERMANENT",
                    "retention_years": None,
                    "confidentiality_max": "INTERNAL",
                    "tenant_id": 999,
                },
            ),
        )
        if pollution.status_code != 422:
            raise JourneyFailure(f"unknown field expected 422, got {pollution.status_code}")
        content = f"governed-http-record-{suffix}".encode()
        attachment = stage(
            "upload_real_attachment_bytes",
            lambda: expect_ok(
                client.post(
                    "/attachments",
                    json={
                        "biz_type": "RECORD_SOURCE",
                        "biz_id": suffix,
                        "filename": "http-record.txt",
                        "content_type": "text/plain",
                        "content_base64": base64.b64encode(content).decode(),
                        "park_id": park["id"],
                    },
                ),
                "upload attachment",
            ),
        )
        record = stage(
            "create_record",
            lambda: expect_ok(
                client.post(
                    "/records",
                    json={
                        "park_id": park["id"],
                        "category_id": category["id"],
                        "title": f"HTTP 受控档案 {suffix}",
                        "description": "合成真实 HTTP 旅程",
                        "confidentiality": "CONFIDENTIAL",
                        "source_type": "LEASE_CONTRACT",
                        "source_id": f"HTTP:{suffix}",
                    },
                ),
                "create record",
            ),
        )
        record = stage(
            "derive_immutable_revision_checksum",
            lambda: expect_ok(
                client.post(
                    f"/records/{record['id']}/revisions",
                    json={
                        "expected_version": record["lock_version"],
                        "attachment_id": attachment["id"],
                    },
                ),
                "add revision",
            ),
        )
        revision = record["revisions"][0]
        if revision["checksum_sha256"] != hashlib.sha256(content).hexdigest():
            raise JourneyFailure("server-derived revision checksum mismatch")
        pinned = stage(
            "block_governed_attachment_delete",
            lambda: client.delete(f"/attachments/{attachment['id']}"),
        )
        expect_error(pinned, 409, "ATTACHMENT_GOVERNED_RECORD_PINNED", "pinned attachment")
        stale = stage(
            "reject_stale_record_version",
            lambda: client.post(
                f"/records/{record['id']}/file",
                json={"expected_version": 1, "reason": "过期客户端"},
            ),
        )
        expect_error(stale, 409, "VERSION_CONFLICT", "stale record")
        record = stage(
            "file_record",
            lambda: expect_ok(
                client.post(
                    f"/records/{record['id']}/file",
                    json={
                        "expected_version": record["lock_version"],
                        "reason": "HTTP 正式归档",
                    },
                ),
                "file record",
            ),
        )
        verify_key = f"verify-{suffix}"
        verified = stage(
            "verify_integrity",
            lambda: expect_ok(
                client.post(
                    f"/records/{record['id']}/verify",
                    headers={"Idempotency-Key": verify_key},
                    json={"revision_id": revision["id"]},
                ),
                "verify record",
            ),
        )
        replay = stage(
            "verify_idempotent_replay",
            lambda: expect_ok(
                client.post(
                    f"/records/{record['id']}/verify",
                    headers={"Idempotency-Key": verify_key},
                    json={"revision_id": revision["id"]},
                ),
                "verify replay",
            ),
        )
        if verified["id"] != replay["id"] or verified["result"] != "MATCH":
            raise JourneyFailure("integrity verification replay changed the result")
        seal = stage(
            "create_seal_with_custody_event",
            lambda: expect_ok(
                client.post(
                    "/seals",
                    json={
                        "park_id": park["id"],
                        "seal_code": f"HTTP-SEAL-{suffix}",
                        "name": "HTTP 合同专用章",
                        "kind": "CONTRACT",
                        "custodian_user_id": login["user"]["id"],
                        "description": "合成 HTTP 台账",
                    },
                ),
                "create seal",
            ),
        )
        if seal["custody_events"][0]["event_type"] != "CREATED":
            raise JourneyFailure("seal creation did not append the custody event")
        provider = stage(
            "create_truthful_sandbox_provider",
            lambda: expect_ok(
                client.post(
                    "/signature-providers",
                    json={
                        "code": f"HTTP_SIG_{suffix}",
                        "name": "HTTP 本地非法律效力沙箱",
                        "adapter_kind": "LOCAL_SANDBOX",
                    },
                ),
                "create sandbox provider",
            ),
        )
        if provider["status"] != "SANDBOX" or provider["live_verified"] is not False:
            raise JourneyFailure("sandbox provider truth was overstated")
        envelope = stage(
            "create_exact_revision_envelope",
            lambda: expect_ok(
                client.post(
                    "/signature-envelopes",
                    json={
                        "provider_id": provider["id"],
                        "record_id": record["id"],
                        "revision_id": revision["id"],
                        "source_type": "LEASE_CONTRACT",
                        "source_id": f"HTTP:{suffix}",
                        "purpose": "HTTP 沙箱签署",
                        "participants": [
                            {
                                "role": "SIGNER",
                                "display_name": "合成签署人",
                                "contact_masked": "138****8000",
                            }
                        ],
                    },
                ),
                "create envelope",
            ),
        )
        envelope = stage(
            "dispatch_non_legal_sandbox",
            lambda: expect_ok(
                client.post(
                    f"/signature-envelopes/{envelope['id']}/dispatch",
                    json={
                        "expected_version": envelope["lock_version"],
                        "reason": "仅验证沙箱流程",
                    },
                ),
                "dispatch envelope",
            ),
        )
        if envelope["status"] != "SANDBOX_COMPLETED" or envelope["live_verified"] is not False:
            raise JourneyFailure("sandbox dispatch was represented as live signing")
        external = stage(
            "declare_external_provider_not_connected",
            lambda: expect_ok(
                client.post(
                    "/signature-providers",
                    json={
                        "code": f"HTTP_EXT_{suffix}",
                        "name": "HTTP 外部签章未连接",
                        "adapter_kind": "EXTERNAL",
                        "credential_ref": None,
                    },
                ),
                "declare external provider",
            ),
        )
        if external["status"] != "NOT_CONNECTED" or external["live_verified"] is not False:
            raise JourneyFailure("external provider was incorrectly marked connected")
        unavailable = stage(
            "fail_closed_external_envelope",
            lambda: client.post(
                "/signature-envelopes",
                json={
                    "provider_id": external["id"],
                    "record_id": record["id"],
                    "revision_id": revision["id"],
                    "source_type": "LEASE_CONTRACT",
                    "source_id": f"HTTP-EXT:{suffix}",
                    "purpose": "禁止伪造外部签章",
                    "participants": [{"role": "SIGNER", "display_name": "合成签署人"}],
                },
            ),
        )
        expect_error(
            unavailable,
            409,
            "SIGNATURE_PROVIDER_UNAVAILABLE",
            "external provider unavailable",
        )
        tenant_b_login = stage(
            "login_other_tenant",
            lambda: expect_ok(
                client.post(
                    "/auth/login",
                    json={
                        "username": "admin_b",
                        "password": "adminb123",
                        "tenant_code": "tenant_b",
                    },
                ),
                "tenant B login",
            ),
        )
        tenant_b = httpx.Client(
            base_url=args.base_url,
            timeout=20.0,
            headers={"Authorization": f"Bearer {tenant_b_login['access_token']}"},
        )
        try:
            isolated = stage(
                "cross_tenant_record_isolation",
                lambda: tenant_b.get(f"/records/{record['id']}"),
            )
            expect_error(isolated, 404, "RECORD_NOT_FOUND", "cross-tenant record")
        finally:
            tenant_b.close()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "synthetic_only": True,
        "record_id": record["id"],
        "seal_id": seal["id"],
        "envelope_id": envelope["id"],
        "stage_count": len(stages),
        "stages": stages,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "passed": all(item["passed"] for item in stages),
        "external_signature_status": external["status"],
        "production_contacted": False,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

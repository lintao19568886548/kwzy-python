#!/usr/bin/env python3
"""Loopback-only real HTTP acceptance for enterprise Party governance."""

from __future__ import annotations

import argparse
import base64
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
        raise JourneyFailure(
            f"{label}: non-JSON response {response.status_code}"
        ) from exc
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
    parser.add_argument(
        "--base-url", type=loopback_url, default="http://127.0.0.1:8010/api/v1"
    )
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
                "X-Client-Platform": "party-enterprise-acceptance-http",
            }
        )
        raw_identifier = f"91310000{suffix[:8]}AB"
        first = stage(
            "create_enterprise_party",
            lambda: expect_ok(
                client.post(
                    "/parties",
                    json={
                        "name": f"HTTP 企业画像甲 {suffix}",
                        "party_type": "ORGANIZATION",
                        "credit_code": raw_identifier,
                    },
                ),
                "create first Party",
            ),
        )
        second = stage(
            "create_related_party",
            lambda: expect_ok(
                client.post(
                    "/parties",
                    json={
                        "name": f"HTTP 企业画像乙 {suffix}",
                        "party_type": "ORGANIZATION",
                    },
                ),
                "create second Party",
            ),
        )
        party_id = int(first["id"])
        second_id = int(second["id"])
        initial = stage(
            "read_initial_profile",
            lambda: expect_ok(
                client.get(f"/parties/{party_id}/enterprise-profile"), "initial profile"
            ),
        )
        if (
            initial["completeness_score"] != 15
            or initial["provider_status"] != "NOT_CONNECTED"
        ):
            raise JourneyFailure("initial completeness/provider state is not truthful")
        profile = stage(
            "save_governed_profile",
            lambda: expect_ok(
                client.put(
                    f"/parties/{party_id}/enterprise-profile",
                    json={
                        "expected_lock_version": 0,
                        "short_name": f"HTTP甲{suffix[:4]}",
                        "legal_representative": "合成负责人",
                        "established_on": "2020-01-02",
                        "registered_capital": "1000000.00",
                        "capital_currency": "CNY",
                        "registration_status": "ACTIVE",
                        "industry_code": "I65",
                        "industry_name": "软件和信息技术服务业",
                        "business_scope": "合成园区数字化服务",
                    },
                ),
                "save profile",
            ),
        )
        stale = stage(
            "reject_stale_profile",
            lambda: client.put(
                f"/parties/{party_id}/enterprise-profile",
                json={"expected_lock_version": 0, "short_name": "过期草稿"},
            ),
        )
        expect_error(stale, 409, "ENTERPRISE_PROFILE_CONFLICT", "stale profile")
        stage(
            "create_registered_address",
            lambda: expect_ok(
                client.post(
                    f"/parties/{party_id}/addresses",
                    json={
                        "address_type": "REGISTERED",
                        "country_code": "CN",
                        "province": "上海市",
                        "city": "上海市",
                        "district": "浦东新区",
                        "detail": "合成园区 1 号",
                        "is_primary": True,
                    },
                ),
                "registered address",
            ),
        )
        stage(
            "create_primary_contact",
            lambda: expect_ok(
                client.post(
                    f"/parties/{party_id}/contacts",
                    json={
                        "name": "合成联系人",
                        "phone": "13800138000",
                        "is_primary": True,
                    },
                ),
                "primary contact",
            ),
        )
        attachment = stage(
            "upload_credential_evidence",
            lambda: expect_ok(
                client.post(
                    "/attachments",
                    json={
                        "biz_type": "PARTY_ENTERPRISE",
                        "biz_id": str(party_id),
                        "filename": "synthetic-license.txt",
                        "content_type": "text/plain",
                        "content_base64": base64.b64encode(
                            b"synthetic enterprise credential evidence"
                        ).decode(),
                    },
                ),
                "upload evidence",
            ),
        )
        credential_response = stage(
            "create_reduced_credential",
            lambda: client.post(
                f"/parties/{party_id}/enterprise-credentials",
                json={
                    "attachment_id": attachment["id"],
                    "credential_type": "BUSINESS_LICENSE",
                    "identifier": raw_identifier,
                    "issuer": "合成市场监督管理机构",
                    "issued_on": "2020-01-02",
                },
            ),
        )
        credential = expect_ok(credential_response, "create credential")
        if (
            raw_identifier in credential_response.text
            or "identifier_fingerprint" in credential_response.text
        ):
            raise JourneyFailure(
                "raw/fingerprint credential identifier leaked through HTTP"
            )
        external_review = stage(
            "forbid_fabricated_external_review",
            lambda: client.post(
                f"/parties/{party_id}/enterprise-credentials/{credential['id']}/review",
                json={
                    "expected_lock_version": credential["lock_version"],
                    "verification_status": "EXTERNALLY_VERIFIED",
                    "reason": "没有真实适配器",
                },
            ),
        )
        expect_error(
            external_review, 409, "EXTERNAL_VERIFICATION_FORBIDDEN", "external review"
        )
        relationship = stage(
            "create_parent_relationship",
            lambda: expect_ok(
                client.post(
                    f"/parties/{party_id}/enterprise-relationships",
                    json={
                        "target_party_id": second_id,
                        "relationship_type": "PARENT_OF",
                        "ownership_percent": "60",
                    },
                ),
                "create relationship",
            ),
        )
        if relationship["ownership_percent"] != "60.00":
            raise JourneyFailure("relationship ownership was not normalized")
        cycle = stage(
            "reject_parent_cycle",
            lambda: client.post(
                f"/parties/{second_id}/enterprise-relationships",
                json={"target_party_id": party_id, "relationship_type": "PARENT_OF"},
            ),
        )
        expect_error(cycle, 409, "ENTERPRISE_RELATIONSHIP_CYCLE", "parent cycle")
        tag = stage(
            "create_provenance_tag",
            lambda: expect_ok(
                client.post(
                    f"/parties/{party_id}/enterprise-tags",
                    json={"name": "专精特新", "tag_type": "QUALIFICATION"},
                ),
                "create tag",
            ),
        )
        repeated_tag = stage(
            "tag_idempotent_reapply",
            lambda: expect_ok(
                client.post(
                    f"/parties/{party_id}/enterprise-tags",
                    json={"name": "专精特新", "tag_type": "QUALIFICATION"},
                ),
                "repeat tag",
            ),
        )
        if tag["id"] != repeated_tag["id"]:
            raise JourneyFailure("tag reapply created a duplicate")
        risk = stage(
            "create_local_risk_signal",
            lambda: expect_ok(
                client.post(
                    f"/parties/{party_id}/enterprise-risk-signals",
                    json={
                        "category": "COMPLIANCE",
                        "severity": "CRITICAL",
                        "summary": "合成 HTTP 合规待核查",
                        "source_reference": f"http-risk-{suffix}",
                    },
                ),
                "create risk",
            ),
        )
        risk_list = stage(
            "verify_local_risk_summary",
            lambda: expect_ok(
                client.get(f"/parties/{party_id}/enterprise-risk-signals"), "list risk"
            ),
        )
        if (
            risk_list["summary"]["overall_level"] != "CRITICAL"
            or first["risk_status"] != "NORMAL"
        ):
            raise JourneyFailure("local risk and blacklist state were conflated")
        stage(
            "resolve_local_risk",
            lambda: expect_ok(
                client.post(
                    f"/parties/{party_id}/enterprise-risk-signals/{risk['id']}/resolve",
                    json={
                        "resolution_type": "MITIGATED",
                        "reason": "HTTP 人工确认已缓释",
                    },
                ),
                "resolve risk",
            ),
        )
        final_profile = stage(
            "verify_complete_profile",
            lambda: expect_ok(
                client.get(f"/parties/{party_id}/enterprise-profile"),
                "complete profile",
            ),
        )
        if final_profile["completeness_score"] != 100:
            raise JourneyFailure(
                f"profile completeness is {final_profile['completeness_score']}, not 100"
            )
        directory = stage(
            "reconcile_filtered_directory",
            lambda: expect_ok(
                client.get(
                    "/enterprise-parties",
                    params={
                        "keyword": suffix,
                        "registration_status": "ACTIVE",
                        "industry": "软件",
                        "min_completeness": 100,
                        "max_completeness": 100,
                    },
                ),
                "filtered directory",
            ),
        )
        if (
            directory["total"] != 1
            or int(directory["items"][0]["party_id"]) != party_id
        ):
            raise JourneyFailure(
                "directory result does not reconcile with source Party"
            )
        pollution = stage(
            "reject_parameter_pollution",
            lambda: client.put(
                f"/parties/{party_id}/enterprise-profile",
                json={
                    "expected_lock_version": profile["lock_version"],
                    "tenant_id": 999,
                    "id_number": "forbidden",
                },
            ),
        )
        if pollution.status_code != 422:
            raise JourneyFailure(
                f"parameter pollution expected 422, got {pollution.status_code}"
            )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "synthetic_only": True,
        "party_id": party_id,
        "stage_count": len(stages),
        "stages": stages,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "passed": all(item["passed"] for item in stages),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

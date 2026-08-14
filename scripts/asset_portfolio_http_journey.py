#!/usr/bin/env python3
"""Loopback-only real HTTP acceptance for templates and asset portfolio views."""

from __future__ import annotations

import argparse
import json
import sys
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
    pass


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


def login(client: httpx.Client, username: str, password: str, tenant_code: str) -> str:
    data = expect_ok(
        client.post(
            "/auth/login",
            json={
                "username": username,
                "password": password,
                "tenant_code": tenant_code,
            },
        ),
        f"login {username}",
    )
    return str(data["access_token"])


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
        token = stage(
            "login",
            lambda: login(client, args.username, args.password, "default"),
        )
        client.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "X-Client-Platform": "asset-portfolio-acceptance-http",
            }
        )
        templates = stage(
            "bootstrap_builtin_templates",
            lambda: expect_ok(client.get("/asset-templates"), "list templates"),
        )
        categories = {row["category"] for row in templates if row["is_builtin"]}
        expected_categories = {
            "FACTORY",
            "WAREHOUSE",
            "SHOP",
            "OFFICE",
            "DORMITORY",
            "PARKING",
            "PUBLIC_SPACE",
        }
        if categories != expected_categories:
            raise JourneyFailure(f"built-in categories mismatch: {categories}")
        repeated = stage(
            "builtin_bootstrap_idempotent",
            lambda: expect_ok(client.get("/asset-templates"), "repeat templates"),
        )
        if {row["id"] for row in repeated} != {row["id"] for row in templates}:
            raise JourneyFailure("built-in bootstrap changed template identity")

        created = stage(
            "create_custom_template_draft",
            lambda: expect_ok(
                client.post(
                    "/asset-templates",
                    json={
                        "code": f"HTTP_OFFICE_{suffix}",
                        "name": f"HTTP 办公模板 {suffix}",
                        "category": "OFFICE",
                        "fields": [
                            {
                                "key": "capacity",
                                "label": "容量",
                                "type": "NUMBER",
                                "required": True,
                                "min": 1,
                                "max": 10000,
                            }
                        ],
                        "defaults": {},
                    },
                ),
                "create template",
            ),
        )
        updated = stage(
            "update_template_draft",
            lambda: expect_ok(
                client.put(
                    f"/asset-templates/{created['id']}/draft",
                    json={
                        "expected_version": created["lock_version"],
                        "description": "经 HTTP 复核的租户模板",
                    },
                ),
                "update template draft",
            ),
        )
        stale_template = stage(
            "template_stale_write_rejected",
            lambda: client.put(
                f"/asset-templates/{created['id']}/draft",
                json={
                    "expected_version": created["lock_version"],
                    "name": "过期窗口不应成功",
                },
            ),
        )
        expect_error(
            stale_template,
            409,
            "ASSET_TEMPLATE_VERSION_CONFLICT",
            "stale template write",
        )
        published = stage(
            "publish_immutable_template_version",
            lambda: expect_ok(
                client.post(
                    f"/asset-templates/{created['id']}/publish",
                    json={"expected_version": updated["lock_version"]},
                ),
                "publish template",
            ),
        )
        template_version_id = int(published["published"]["id"])

        unsafe = stage(
            "unsafe_template_grammar_rejected",
            lambda: client.post(
                "/asset-templates",
                json={
                    "code": f"UNSAFE_{suffix}",
                    "name": "不安全模板",
                    "category": "OFFICE",
                    "fields": [
                        {
                            "key": "callback",
                            "label": "https://unsafe.example",
                            "type": "TEXT",
                        }
                    ],
                },
            ),
        )
        expect_error(unsafe, 400, "ASSET_TEMPLATE_INVALID", "unsafe template")

        park = stage(
            "create_park",
            lambda: expect_ok(
                client.post(
                    "/parks",
                    json={"name": f"HTTP 资产组合园 {suffix}", "address": "loopback"},
                ),
                "create park",
            ),
        )
        geometry = {
            "type": "Polygon",
            "coordinates": [[[10, 10], [210, 10], [210, 130], [10, 130], [10, 10]]],
        }
        space = stage(
            "create_real_geometry_space",
            lambda: expect_ok(
                client.post(
                    "/spaces",
                    json={
                        "park_id": park["id"],
                        "code": f"HTTP-B-{suffix}",
                        "name": f"HTTP 几何楼栋 {suffix}",
                        "node_type": "BUILDING",
                        "geometry": geometry,
                        "coordinate_reference": "LOCAL",
                    },
                ),
                "create geometry space",
            ),
        )
        unit = stage(
            "create_template_bound_unit",
            lambda: expect_ok(
                client.post(
                    "/units",
                    json={
                        "park_id": park["id"],
                        "building_id": space["id"],
                        "code": f"HTTP-U-{suffix}",
                        "name": "HTTP 模板办公单元",
                        "rentable_area": 88,
                        "base_rent_price": 10,
                        "usage_type": "OFFICE",
                        "asset_template_version_id": template_version_id,
                        "attributes": {"capacity": 12},
                    },
                ),
                "create template unit",
            ),
        )
        if int(unit["asset_template_version_id"]) != template_version_id:
            raise JourneyFailure("unit did not preserve exact template version")

        map_data = stage(
            "map_projection_from_stored_geometry",
            lambda: expect_ok(
                client.get("/rent-control/map", params={"park_id": park["id"]}),
                "map projection",
            ),
        )
        if (
            map_data["provider_status"] != "NOT_CONNECTED_LOCAL_SCHEMATIC"
            or map_data["coordinate_references"] != ["LOCAL"]
            or len(map_data["features"]) != 1
            or map_data["features"][0]["geometry"] != geometry
        ):
            raise JourneyFailure("map is not a faithful provider-neutral geometry projection")
        vacancies = stage(
            "vacancy_projection",
            lambda: expect_ok(
                client.get("/rent-control/vacancies", params={"park_id": park["id"]}),
                "vacancies",
            ),
        )
        if vacancies["total"] != 1 or vacancies["items"][0]["available_area"] != 88:
            raise JourneyFailure("vacancy projection does not reconcile with unit area")
        analysis = stage(
            "portfolio_analysis_reconciliation",
            lambda: expect_ok(
                client.get("/rent-control/analysis", params={"park_id": park["id"]}),
                "analysis",
            ),
        )
        office = next(row for row in analysis["categories"] if row["key"] == "OFFICE")
        if (
            analysis["summary"]["rentable_area"] != 88
            or analysis["asking_rent_potential"] != 880
            or office["available_area"] != 88
            or "非会计" not in analysis["asking_rent_potential_label"]
        ):
            raise JourneyFailure("portfolio analysis failed source-row reconciliation")

        moved = stage(
            "geometry_optimistic_update",
            lambda: expect_ok(
                client.patch(
                    f"/spaces/{space['id']}",
                    json={
                        "geometry": {"type": "Point", "coordinates": [30, 40]},
                        "coordinate_reference": "LOCAL",
                        "expected_geometry_version": space["geometry_version"],
                    },
                ),
                "update geometry",
            ),
        )
        if moved["geometry_version"] != 2:
            raise JourneyFailure("geometry version did not advance")
        stale_geometry = stage(
            "geometry_stale_write_rejected",
            lambda: client.patch(
                f"/spaces/{space['id']}",
                json={
                    "geometry": {"type": "Point", "coordinates": [50, 60]},
                    "coordinate_reference": "LOCAL",
                    "expected_geometry_version": 1,
                },
            ),
        )
        expect_error(
            stale_geometry,
            409,
            "SPACE_GEOMETRY_VERSION_CONFLICT",
            "stale geometry",
        )

        next_unit = stage(
            "create_structural_version_with_template_history",
            lambda: expect_ok(
                client.post(
                    f"/units/{unit['id']}/versions",
                    json={
                        "expected_lock_version": unit["lock_version"],
                        "rentable_area": 100,
                        "asset_template_version_id": template_version_id,
                        "attributes": {"capacity": 20},
                    },
                ),
                "create unit version",
            ),
        )
        history = stage(
            "verify_unit_version_history",
            lambda: expect_ok(
                client.get(f"/units/{next_unit['id']}/history"),
                "unit history",
            ),
        )
        if [row["version_no"] for row in history] != [2, 1] or any(
            int(row["asset_template_version_id"]) != template_version_id for row in history
        ):
            raise JourneyFailure("unit history lost its exact template version binding")

        viewer_token = stage(
            "login_read_only_asset_user",
            lambda: login(client, "e2e_asset_viewer", "viewer123", "default"),
        )
        viewer_headers = {
            "Authorization": f"Bearer {viewer_token}",
            "X-Permissions": "asset.template.write",
        }
        forged_write = stage(
            "forged_template_write_permission_rejected",
            lambda: client.post(
                "/asset-templates",
                headers=viewer_headers,
                json={
                    "code": f"FORGED_{suffix}",
                    "name": "伪造权限模板",
                    "category": "OFFICE",
                },
            ),
        )
        expect_error(
            forged_write,
            403,
            "PERMISSION_DENIED",
            "forged write permission",
        )

        tenant_b_token = stage(
            "login_second_tenant",
            lambda: login(client, "admin_b", "adminb123", "tenant_b"),
        )
        cross_tenant = stage(
            "cross_tenant_template_idor_hidden",
            lambda: client.get(
                f"/asset-templates/{created['id']}",
                headers={"Authorization": f"Bearer {tenant_b_token}"},
            ),
        )
        expect_error(cross_tenant, 404, "ASSET_TEMPLATE_NOT_FOUND", "template IDOR")

    report = {
        "schema_version": 1,
        "result": "PASS",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "target": args.base_url,
        "real_http": True,
        "external_map_provider": "NOT_CONNECTED_LOCAL_SCHEMATIC",
        "template_id": created["id"],
        "template_version_id": template_version_id,
        "park_id": park["id"],
        "space_id": space["id"],
        "unit_id": next_unit["id"],
        "stages": stages,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ASSET_PORTFOLIO_HTTP_REPORT={output}")
    print("ASSET_PORTFOLIO_REAL_HTTP=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"ASSET_PORTFOLIO_REAL_HTTP=FAIL error={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise

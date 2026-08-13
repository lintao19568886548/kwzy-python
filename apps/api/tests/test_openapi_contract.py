"""OpenAPI 3.1 严格校验与 Step1/Party 路由一致性检查。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]  # kwzy-python
OPENAPI_PATH = ROOT / "docs" / "04-api" / "openapi-v1-core.yaml"


def _iter_api_paths(app) -> set[str]:
    """收集运行时 /api/v1 路径（含 include_router 嵌套）。"""
    paths: set[str] = set()

    def walk(routes, prefix: str = "") -> None:
        for route in routes:
            path = getattr(route, "path", None)
            nested = getattr(route, "routes", None)
            if nested is not None and path is None:
                # FastAPI _IncludedRouter
                walk(nested, prefix)
                continue
            if path is None:
                continue
            full = prefix + path if not path.startswith(prefix) else path
            # include_router 挂在 prefix 上时，子路由 path 可能已是完整或相对
            paths.add(full)
            if nested is not None:
                walk(nested, full.rstrip("/"))

    walk(app.routes)
    # 补齐：从 openapi schema 导出更可靠
    try:
        schema = app.openapi()
        for p in schema.get("paths") or {}:
            paths.add(p)
    except Exception:
        pass
    return {p for p in paths if p and ("/api/" in p or p.startswith("/parties") or p.startswith("/parks") or p.startswith("/auth") or p.startswith("/units"))}


def test_openapi_v1_core_is_valid_openapi_31() -> None:
    pytest.importorskip("openapi_spec_validator")
    from openapi_spec_validator import validate
    from openapi_spec_validator.readers import read_from_filename

    assert OPENAPI_PATH.is_file(), f"missing {OPENAPI_PATH}"
    spec, _ = read_from_filename(str(OPENAPI_PATH))
    validate(spec)
    assert str(spec.get("openapi", "")).startswith("3.")


def test_party_schema_has_no_master_park_id_or_address() -> None:
    """契约：Party 主档不得含 park_id 归属字段与模糊 address。"""
    doc = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    schemas = (doc.get("components") or {}).get("schemas") or {}
    party = schemas.get("Party") or {}
    props = party.get("properties") or {}
    assert "park_id" not in props, "Party schema must not have master park_id"
    assert "address" not in props, "Party schema must not have master free-form address"
    create = schemas.get("PartyCreate") or {}
    cprops = create.get("properties") or {}
    assert "park_id" not in cprops
    assert "address" not in cprops
    assert "initial_park_relation" in cprops
    assert "InitialParkRelation" in schemas
    assert "/parties/{party_id}/addresses" in (doc.get("paths") or {})
    assert "/parties/{party_id}/park-relations" in (doc.get("paths") or {})


def test_step1_runtime_paths_covered_by_openapi() -> None:
    """运行时路由应出现在 OpenAPI 契约中。"""
    from app.main import create_app

    assert OPENAPI_PATH.is_file()
    doc = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = set(doc.get("paths") or {})

    app = create_app()
    runtime = _iter_api_paths(app)
    # OpenAPI 可能省略 prefix；同时兼容带/不带 /api/v1
    openapi_with_prefix = set()
    for p in paths:
        openapi_with_prefix.add(p)
        if not p.startswith("/api/"):
            openapi_with_prefix.add("/api/v1" + p if p.startswith("/") else "/api/v1/" + p)
        openapi_with_prefix.add(p.replace("/api/v1", "", 1) if p.startswith("/api/v1") else p)

    required_markers = (
        "/auth/login",
        "/parks",
        "/units",
        "/parties",
        "/leases",
        "/bills",
        "/payments",
        "/work-items",
        "/workbench/summary",
        "/leads",
    )
    for marker in required_markers:
        assert any(marker in p for p in paths) or any(
            marker in p for p in runtime
        ), f"missing coverage for {marker}"

    # 每个 runtime path 的路径模板应能在 openapi 中找到对应资源
    for rp in runtime:
        if rp in {"/api/v1/openapi.json", "/openapi.json"}:
            continue
        bare = rp.replace("/api/v1", "") or "/"
        # path params: {id} vs concrete — use prefix match on resource root
        resource = bare.split("{")[0].rstrip("/")
        if not resource or resource == "/":
            continue
        # skip health and docs
        if resource in {"/health", "/docs", "/redoc"}:
            continue
        found = any(
            resource in op or resource in op.replace("/api/v1", "")
            for op in openapi_with_prefix
        )
        assert found, f"runtime route {rp} not reflected in OpenAPI ({resource})"

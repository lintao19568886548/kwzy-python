"""OpenAPI 3.1 严格校验与 Step1 路由一致性检查。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]  # kwzy-python
OPENAPI_PATH = ROOT / "docs" / "04-api" / "openapi-v1-core.yaml"


def test_openapi_v1_core_is_valid_openapi_31() -> None:
    pytest.importorskip("openapi_spec_validator")
    from openapi_spec_validator import validate
    from openapi_spec_validator.readers import read_from_filename

    assert OPENAPI_PATH.is_file(), f"missing {OPENAPI_PATH}"
    spec, _ = read_from_filename(str(OPENAPI_PATH))
    validate(spec)
    assert str(spec.get("openapi", "")).startswith("3.")


def test_step1_runtime_paths_covered_by_openapi() -> None:
    """运行时 Step1 路由应出现在 OpenAPI 契约中（非 Party 扩展）。"""
    from app.main import create_app

    assert OPENAPI_PATH.is_file()
    doc = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    paths = set(doc.get("paths") or {})

    app = create_app()
    runtime = {
        getattr(route, "path", "")
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/v1")
    }
    # OpenAPI 可能省略 prefix；同时兼容带/不带 /api/v1
    openapi_with_prefix = set()
    for p in paths:
        openapi_with_prefix.add(p)
        if not p.startswith("/api/"):
            openapi_with_prefix.add("/api/v1" + p if p.startswith("/") else "/api/v1/" + p)
        openapi_with_prefix.add(p.replace("/api/v1", "", 1) if p.startswith("/api/v1") else p)

    required_markers = ("/auth/login", "/parks", "/units")
    for marker in required_markers:
        assert any(marker in p for p in paths) or any(
            marker in p for p in runtime
        ), f"missing coverage for {marker}"

    # 每个 runtime path 的路径模板应能在 openapi 中找到对应资源
    for rp in runtime:
        if rp in {"/api/v1/openapi.json"}:
            continue
        bare = rp.replace("/api/v1", "") or "/"
        # path params: {id} vs concrete — use prefix match on resource root
        resource = bare.split("{")[0].rstrip("/")
        if not resource or resource == "/":
            continue
        found = any(
            resource in op or resource in op.replace("/api/v1", "")
            for op in openapi_with_prefix
        )
        assert found, f"runtime route {rp} not reflected in OpenAPI ({resource})"

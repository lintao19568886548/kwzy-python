"""分层架构静态检查：Application 不得直接依赖 ORM models。"""

from __future__ import annotations

from pathlib import Path

FORBIDDEN_IMPORT_SNIPPETS = (
    "from app.infrastructure.database.models",
    "import app.infrastructure.database.models",
)

# bootstrap 明确允许在 identity application 种子中使用 ORM（文档白名单）
ALLOWLIST_SUFFIXES = (
    "identity/application/bootstrap.py",
    "identity\\application\\bootstrap.py",
)


def test_application_layer_does_not_import_orm_models() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "modules"
    violations: list[str] = []
    for path in root.rglob("*.py"):
        if "application" not in path.parts:
            continue
        rel = str(path.relative_to(root))
        if any(rel.endswith(s) or rel.replace("\\", "/").endswith(s.replace("\\", "/")) for s in ALLOWLIST_SUFFIXES):
            continue
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_IMPORT_SNIPPETS:
            if snippet in text:
                violations.append(f"{rel}: contains `{snippet}`")
    assert not violations, "Application 层禁止导入 ORM models:\n" + "\n".join(violations)


def test_lease_application_does_not_import_foreign_context_infrastructure() -> None:
    lease_application = (
        Path(__file__).resolve().parents[1] / "app" / "modules" / "lease" / "application"
    )
    forbidden = (
        "app.modules.attachments.infrastructure",
        "app.modules.investment.infrastructure",
        "app.modules.park_property.infrastructure",
        "app.modules.party.infrastructure",
        "app.modules.workflow.infrastructure",
        "app.modules.workbench.application",
        "app.modules.workbench.infrastructure",
    )
    violations: list[str] = []
    for path in lease_application.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for snippet in forbidden:
            if snippet in text:
                violations.append(f"{path.name}: contains `{snippet}`")
    assert not violations, "Lease application must use owned collaboration ports:\n" + "\n".join(
        violations
    )


def test_integration_router_has_no_orm_or_private_session_access() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "modules"
        / "platform_integrations"
        / "interface"
        / "api.py"
    )
    text = path.read_text(encoding="utf-8")
    forbidden = (
        "from sqlalchemy import select",
        "app.infrastructure.database.models",
        "SessionLocal",
        ".query(",
        ".scalars(",
    )
    violations = [snippet for snippet in forbidden if snippet in text]
    assert not violations, f"integration router bypasses application boundary: {violations}"

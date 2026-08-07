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

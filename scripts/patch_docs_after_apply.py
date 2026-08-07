# -*- coding: utf-8 -*-
"""One-shot doc patches after close-step1-acceptance-gaps apply."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_schema_notes() -> None:
    p = ROOT / "docs/03-database/02-schema-notes.md"
    text = p.read_text(encoding="utf-8")
    if "3.1 运行真相" in text:
        print("schema notes already patched")
        return
    needle = "**明确不上 v1 主链的表：**"
    insert = """### 3.1 运行真相：Alembic（Step1）

| 项 | 说明 |
| --- | --- |
| 权威来源 | `apps/api/alembic/versions/*` + ORM models；**不以设计 DDL 静默改库** |
| Step1 head | `9f17fd2e9180`（`all_parks` 列；前序 `8c2f4aa10b7d` 含 RBAC/audit） |
| `roles.all_parks` / `users.all_parks` | Boolean，默认 false；ADMIN 种子/迁移回填 true |
| `permissions` | 全局权限码字典；`*` 仅动作超级权限 |
| 园区范围表 | `user_park_scopes` / `role_park_scopes`（租户过滤并集） |

设计 SQL（`01-core-ddl-v1*.sql`）与 live migration 有差距时，**以 Alembic 为准**并回写文档。

"""
    if needle not in text:
        raise SystemExit("schema notes needle missing")
    p.write_text(text.replace(needle, insert + needle, 1), encoding="utf-8")
    print("schema notes updated")


def patch_acceptance() -> None:
    p = ROOT / "docs/06-implementation/phase06-step1-foundation-acceptance-report.md"
    t = p.read_text(encoding="utf-8")
    if "STEP1-ACCEPTANCE-GAPS-CLOSED" in t:
        print("acceptance already updated")
        return
    t += """

---

## 后记：close-step1-acceptance-gaps（2026-08-07）

> 历史验收结论「有条件通过」保留；本后记记录缺口关闭结果，**不覆盖上文正文**。

| 原缺口 | 关闭结果 |
| --- | --- |
| alembic current ≠ head | 已升级至 `9f17fd2e9180`（含 `8c2f4aa10b7d` RBAC/audit + `all_parks`） |
| 固定管理员明文密码 | 移除；`LOCAL_ADMIN_PASSWORD`；test fixture；production 禁止种子 |
| `*` 兼全园 | BREAKING：改为 `park_scope_mode` + `roles/users.all_parks` |
| Application 构造 ORM | Park/Unit 改为 Entity+Mapper；架构测试禁止 application 导入 models（bootstrap 白名单） |
| 日志 `business_module` | JSON 输出规范字段 `module`，过渡双写 `business_module` |
| OpenAPI 未严格校验 | `openapi-spec-validator` + 路由一致性测试 |
| 无 Git 保护 | 根目录 `.gitignore` + `step1-git-runbook.md`（不自动 init） |

**pytest：** 35 passed（含授权矩阵与架构/OpenAPI）。  
**文档追踪：** `step1-document-traceability.md` → STEP1-DOCUMENT-TRACEABILITY-COMPLETE  

```text
STEP1-ACCEPTANCE-GAPS-CLOSED
```
"""
    p.write_text(t, encoding="utf-8")
    print("acceptance postscript added")


def patch_complete() -> None:
    p = ROOT / "docs/06-implementation/phase06-step1-complete.md"
    ct = p.read_text(encoding="utf-8")
    if "close-step1-acceptance-gaps" in ct:
        print("complete already has postscript")
        return
    ct += """

---

## 后记（2026-08-07）close-step1-acceptance-gaps

在不动 Party/Lease/Bill/Payment 前提下关闭验收缺口：DB head、无密钥 bootstrap、权限/园区正交、DDD Entity+Mapper、日志 module、OpenAPI 校验与 Git runbook。  
授权语义变更原因：纠正 `*` 误授全园；ADR-005 与 07 测试规范同步修订。详见验收报告后记。
"""
    p.write_text(ct, encoding="utf-8")
    print("complete postscript added")


def patch_domain_overview() -> None:
    p = ROOT / "docs/02-domain-design/01-domain-overview.md"
    if not p.exists():
        print("domain overview missing")
        return
    t = p.read_text(encoding="utf-8")
    if "park_scope_mode" in t or "all_parks" in t:
        print("domain overview already mentions all_parks")
        return
    # non-blocking: append note if section 5.2 exists
    marker = "园区范围"
    if marker in t and "### 附录" not in t[-500:]:
        t += """

---

## 附录（2026-08-07）园区范围与动作权限

- 动作权限：`permissions` 列表；`*` = 全部动作，**不**表示全园区。  
- 园区范围：`user_park_scopes ∪ role_park_scopes`；全园仅 `roles.all_parks` / `users.all_parks` → `park_scope_mode=ALL`。  
- 详见 ADR-005 修订与 `close-step1-acceptance-gaps`。
"""
        p.write_text(t, encoding="utf-8")
        print("domain overview appendix added")
    else:
        print("domain overview skipped")


def main() -> None:
    patch_schema_notes()
    patch_acceptance()
    patch_complete()
    patch_domain_overview()


if __name__ == "__main__":
    main()

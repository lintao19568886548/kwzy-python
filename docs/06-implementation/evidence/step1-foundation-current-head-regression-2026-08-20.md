# Step1 基础能力当前 HEAD 回归记录

> 验证日期：2026-08-20（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`
> 被验证代码 HEAD：`3e3c815285025e0462122cbc845c447995c28aaf`

## 结论

历史 `harden-step1-foundation` 仅作为早期能力基线，本次没有重新 propose/apply。当前代码仍保留 RBAC、园区授权、统一异常 envelope、`request_id`、结构化业务日志、成功事务审计、生产配置保护和 Park/Unit 权限，定向回归为 `39 passed`，未发现需要新 repair change 的退化。

该结论不覆盖 Party、Lease、Bill、Payment，也不代表完整重构完成。

## PostgreSQL 16 与 Alembic 实测

- 重建仓库专用隔离容器和命名测试卷 `kwzy_party_test_pg` / `kwzy_party_test_pgdata`，未接触生产。
- 服务端版本：PostgreSQL `16.14 (Debian 16.14-1.pgdg13+1)`。
- 空库依次执行 `44cb70117ff4 → 8c2f4aa10b7d → 9f17fd2e9180`，确认旧 Step1 revision 可落地。
- 从 `9f17fd2e9180` 继续执行当前全部前向 migration，最终唯一 head 与 current 均为 `d6a13e9f0b98`。
- 本次没有修改任何历史 migration，也没有使用 `kwzy_step1.db` 的文字记录或本地状态作为通过依据。

## 回归范围

```text
tests/test_identity_authorization.py
tests/test_foundation_compliance.py
tests/test_isolation.py
tests/test_park_unit.py
tests/test_database_runtime_config.py
tests/test_approval_audit_postgres.py
```

执行结果：`39 passed, 51 warnings in 20.87s`。警告均为既有 Starlette/httpx 或 naive UTC 弃用提示，本次没有失败或跳过。

## 边界

- `harden-step1-foundation` 的历史 14/14 和 23 passed 只说明当时状态，不替代本次实测。
- 当前全项目仍有未关闭 P1、缺失能力、真实旧数据迁移和外部适配器门禁；禁止据此合并 main 或宣布全量完成。

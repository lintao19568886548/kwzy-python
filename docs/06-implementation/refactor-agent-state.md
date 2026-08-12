# KWZY Python 自治重构状态

| 字段 | 值 |
| --- | --- |
| 更新时间 | 2026-08-12 |
| 当前分支 | `feat/identity-system-admin` |
| 基线 HEAD | `6090c97` (main/origin/main) |
| 当前阶段 | Identity/System/Admin 实现 |
| 当前领域 | Identity / RBAC / Menu / Session |
| OpenSpec design | `complete-identity-system-admin`（设计+证据，tasks 未勾选） |
| OpenSpec implement | `implement-identity-system-admin`（实现 change） |
| V2.3.2 证据 | READY_FOR_HUMAN_REVIEW（包外 artifacts，不作为 apply 门禁阻塞） |
| 部署 | **未部署** |
| 生产迁移 | **NOT_EXECUTED** |
| 允许合并 | 本分支全量测试通过后方可 |

## 已确认基线

- Party / Lease / Bill / Payment 已在 main
- Identity 现状：login + me + fail-closed JWT + park scope
- 旧 Java 根：`D:\重构python\kwzg-Java-main`（只读）
- origin：`https://github.com/lintao19568886548/kwzy-python.git`

## 下一步

1. 实现 refresh/logout/password + user/role/menu 管理
2. Alembic 单 head 迁移
3. pytest 全量回归
4. 继续剩余领域（园区完善、招商、工单等）

## 永久门禁

- 无 force push / reset --hard
- 无生产 DB / 真实密钥
- 无 STUB 冒充 COMPLETE

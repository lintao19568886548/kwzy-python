# KWZY Python 重构最终验收包（续跑更新）

> 更新时间：2026-08-13  
> 状态：**代码重构进行中**；**未部署生产**。  
> 禁止将「主链 pytest 通过」等同「全系统完成」。

---

## 1. 当前代码基线

| 项 | 值 |
| --- | --- |
| 起点 main | `bc174e5` |
| 工作分支 | `feat/full-rebuild-continue` |
| Alembic head | `c9a57b2d0f31` |
| 后端主链 | Auth → Park/Unit → Party → Lease → Bill → Payment → Workbench |
| 前端 | `apps/web` 脚手架（登录/工作台/列表） |
| ETL | `tools/etl` dry-run 骨架 |

## 2. 完成范围（已交付）

| 能力 | 状态 |
| --- | --- |
| Party/Lease/Bill/Payment v1 | COMPLETE（scoped） |
| Identity 会话+用户角色菜单 API | PARTIAL |
| Workbench CRUD | COMPLETE（API） |
| 账单待办闭环 | COMPLETE |
| 合同到期待办 + summary | COMPLETE（本批） |
| 前端全量 | NOT_COMPLETE |
| ETL 字段闭合 | NOT_READY |
| 招商/工单 | STUB |

## 3. 诚实门禁

| 标识 | 值 |
| --- | --- |
| `KWZY_PYTHON_CODE_REFACTOR` | `IN_PROGRESS` |
| `KWZY_FULL_JAVA_REPLACEMENT` | `IN_PROGRESS` |
| `KWZY_FULL_FRONTEND_REPLACEMENT` | `NOT_COMPLETE` |
| `KWZY_DATA_MIGRATION_READINESS` | `NOT_READY` |
| `KWZY_STAGING_ACCEPTANCE` | `NOT_RUN` |
| `KWZY_PRODUCTION_MIGRATION` | `NOT_EXECUTED` |
| `KWZY_PRODUCTION_DEPLOYMENT` | `NOT_EXECUTED` |
| `KWZY_FULL_REBUILD_ACCEPTANCE` | `BLOCKED` |

### 阻塞项（修复顺序）

1. 前端主旅程/权限/E2E 闭合  
2. 旧 Java 剩余域（招商、工单、通知、审批、报表…）  
3. 字段映射闭合 + 脱敏全量 ETL 演练  
4. PG16 非 skip 全量测试  
5. 预发布验收  
6. 生产迁移与部署（人工权限）

## 4. 回滚

- 应用：回退 git tag / 部署镜像  
- 库：`alembic downgrade` 逐级；生产勿跳 revision  
- 数据：写操作依赖 audit_logs  

## 5. 生产前人工清单

- [ ] 审查 PR 与密钥扫描  
- [ ] 预发 PG16 upgrade head  
- [ ] 脱敏 ETL 对账报告签字  
- [ ] 回滚演练  
- [ ] 生产窗口与备份确认  

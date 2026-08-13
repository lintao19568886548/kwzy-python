# KWZY Python 重构最终验收包

> 更新时间：2026-08-13  
> 分支：`feat/browser-e2e-full-stack`  
> 状态：内部自动化主链（浏览器 E2E + ETL 规模）已闭合；**未做真实外部联调/远程预发/生产**。

---

## 1. 当前代码基线

| 项 | 值 |
| --- | --- |
| 起点 main | `ce9b711` |
| 工作分支 | `feat/browser-e2e-full-stack` |
| Alembic head | `g3b91f6d4c75`（outbox/attachments） |
| 后端主链 | Auth → Park/Unit → Party → Lease → Bill → Payment → Workbench → Leads → WO → Collection → System |
| 前端 | `apps/web` production build + 权限导航 + 全业务表单 |
| 浏览器 E2E | Playwright globalSetup 自动拉 PG16/API/FE；24 specs 全过，禁止 skip |
| ETL | fast 1k+/5k+ 与 acceptance 10k/50k+ 演练 PASS |

## 2. 已交付

| 能力 | 状态 |
| --- | --- |
| Party/Lease/Bill/Payment | COMPLETE + 浏览器验收 |
| Identity 用户/角色/组织/字典/参数 | COMPLETE + 浏览器验收 |
| Workbench/待办闭环 | COMPLETE + 浏览器验收 |
| 招商线索 | COMPLETE + 浏览器验收 |
| 工单/催缴 | COMPLETE + 浏览器验收 |
| Fake 外部适配器 + outbox | ADAPTER_COMPLETE |
| 前端全量替换 | COMPLETE（浏览器主链） |
| ETL 规模演练 | READY_FOR_STAGING_DATA |

## 3. 门禁

| 标识 | 值 |
| --- | --- |
| `KWZY_PYTHON_CODE_REFACTOR` | `COMPLETE`（待 merge main 后固化） |
| `KWZY_FULL_JAVA_REPLACEMENT` | `COMPLETE_PENDING_LIVE_EXTERNAL_VERIFICATION` |
| `KWZY_FULL_FRONTEND_REPLACEMENT` | `COMPLETE` |
| `KWZY_DATA_MIGRATION_READINESS` | `READY_FOR_STAGING_DATA` |
| `KWZY_LOCAL_STAGING_EQUIVALENT` | `PENDING_FULL_RUNNER`（脚本已升级，完整一键待复跑） |
| `KWZY_CODE_REBUILD_ACCEPTANCE` | `PASS`（浏览器 E2E + ETL 规模 + 后端主链证据） |
| `LIVE_EXTERNAL_INTEGRATION` | `NOT_VERIFIED` |
| `KWZY_REMOTE_STAGING_ACCEPTANCE` | `NOT_RUN` |
| `KWZY_PRODUCTION_MIGRATION` | `NOT_EXECUTED` |
| `KWZY_PRODUCTION_DEPLOYMENT` | `NOT_EXECUTED` |
| `KWZY_FULL_REBUILD_ACCEPTANCE` | `BLOCKED_EXTERNAL_ACCEPTANCE` |

## 4. 一键命令

```powershell
# 浏览器全栈 E2E（自动 PG16 + API + production FE）
pwsh scripts/run_browser_e2e.ps1

# ETL 快速档 / 验收档
apps\api\.venv\Scripts\python.exe tools\etl\run_etl_drill.py --profile fast
apps\api\.venv\Scripts\python.exe tools\etl\run_etl_drill.py --profile acceptance

# 本地预发布全量（含 pytest + Playwright + ETL）
pwsh infra\local-staging\run_full_acceptance.ps1
```

## 5. 生产前人工清单

- [ ] 审查 PR 与密钥扫描  
- [ ] 预发 PG16 upgrade head  
- [ ] 脱敏 ETL 对账报告签字  
- [ ] 真实外部凭据联调  
- [ ] 回滚演练  
- [ ] 生产窗口与备份确认  

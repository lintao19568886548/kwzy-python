# 平台组织治理纵切验收证据

> 执行时间：2026-08-14 12:43:27–12:50:03（Asia/Shanghai）
> 执行基线：`37d7cf7da768eef8d7bcc743635117b8f34c7bbb` 加当前组织治理整改工作树
> 判定：本纵切 25/25 自动闸门通过；全项目仍为 `CONDITIONAL/BLOCKED`。

## 本纵切范围

- 集团、区域生命周期与有效期园区归属历史；
- 岗位、主/兼职任职与“任职不授予权限”边界；
- `USER.phone` 受保护字段白名单、最严格多角色优先级和服务端投影；
- PC 组织治理工作区，含桌面、平板只读和移动失败重试；
- PostgreSQL 16 约束/并发、OpenAPI、合成 ETL 和旧系统处置。

## 自动验收结果

| 类别 | 结果 |
| --- | --- |
| 总闸门 | 25/25 exit 0，395489 ms |
| PostgreSQL 16 | fresh upgrade 到唯一 head `n0c68d3e5f42`；downgrade -1 后 re-upgrade PASS |
| 后端测试 | 253 passed |
| 前端 | ESLint、Vue typecheck、6 Vitest、production build 全 PASS |
| 浏览器 | Playwright 43 passed；组织治理 3 条包含真实 HTTP/DB/UI |
| OpenAPI / OpenSpec | 7 tests + YAML strict PASS；50/50 strict PASS |
| 性能 | 1000 请求、并发 25、p95 356.22 ms、118.296 RPS、0% 错误 |
| 备份恢复 | dump 985808 bytes；恢复 65 tables；PASS |
| 敏感信息 | 650 个 tracked/untracked non-ignored 文件扫描 PASS |

## 组织治理 ETL

合成 schema `kwzy.organization-governance.synthetic.v1` 完成 dry-run、首次 apply、幂等重跑、对账和 rollback。首次写入集团/区域/园区归属/岗位/任职/字段策略分别为 `1/2/3/2/2/2`，重复执行均为 0；当前区域重复和当前主岗位重复均为 0；未产生授权关系行或原始 PII；回滚后 fixture schema 不存在。

真实旧库迁移仍为 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`，不以合成演练冒充完成。

## 视觉证据

- `pc-desktop-organization-governance.png`：桌面完整管理旅程；
- `pc-tablet-readonly-governance.png`：平板只读、权限说明与键盘可达；
- `pc-mobile-retry-governance.png`：移动端 503/重试恢复、无横向溢出。

## 组合能力边界

22 条关键旅程中的“集团、区域、园区、角色、用户”已升级为 `IMPLEMENTED_AND_VERIFIED`。20 项产品能力中的“组织/RBAC/园区范围/审批/审计”仍为 `MISSING`，因为完整审批中心和审计中心尚未闭环；本证据不得被解释为全量重构完成。

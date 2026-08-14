# 平台审批与审计中心纵切验收证据

> 工作树验收日期：2026-08-14（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`；clean-SHA 复验 `13243b4488a79ee6eccfc505812b5315263d7c83`
> 判定：平台审批/审计组合能力已实现并经真实栈验证；全项目仍为 `CONDITIONAL/BLOCKED`，真实旧数据与生产均未获授权。

## 交付范围

- 草稿、不可变发布版本、有序 ANY/阈值 ALL 节点、用户/角色审批人和安全停用；
- 稳定审批任务、多步推进、驳回/退回/撤回/重提、自审批门禁、乐观锁和幂等；
- 有效期委托、原审批人/实际操作者证据、SLA 升级与 WorkItem 投影；
- 事务内审计递增序列、递归脱敏、租户链头、SHA-256、独立验证和公式安全 CSV；
- PC 申请/待办/定义/委托/审计五区真实 API 工作区及桌面、平板、移动状态；
- PostgreSQL 16 并发约束、OpenAPI、真实 HTTP、浏览器、合成 ETL 和迁移降升级。

## 已完成的独立闸门

| 类别 | 当前证据 |
| --- | --- |
| Alembic | 唯一 head `o1d79e4f6a53`；fresh upgrade、`downgrade -1 → upgrade head`、current=heads 通过；并修复任务投影在降升级后残留导致的 ID 冲突 |
| 后端 | 聚焦状态机/安全 6 条、审批/组织 PostgreSQL 并发 7 条通过；clean-SHA 完整后端 `264 passed, 1 warning`，97.22 秒 |
| 前端聚焦 | ESLint、Vue typecheck、6 Vitest、production build 通过 |
| 浏览器 | 审批聚焦 3/3、完整真栈 46/46：定义→委托→申请→受托决定→已处理回看→审计/导出、已发布只读、平板只读/伪造权限 403、移动 503/重试；409 时表单保持 |
| 真实 HTTP | clean-SHA 13 阶段 799.63 ms：登录、定义、发布、提交与重复提交、任务、决定与重复决定、审计查询/校验/导出、详情均通过 |
| ETL | dry-run、中断恢复、首次 apply、零重复、9 表逐项对账、零原始 PII、零伪造决定、授权行不变和 rollback 全通过 |
| OpenAPI | 21 条审批/审计路由的 runtime/YAML 方法与 schema 断言及 strict validator 通过 |
| 性能 | clean-SHA 真实 HTTP 1,000 请求、并发 25、失败 0、p95 306.849 ms、128.659 RPS，门槛通过 |
| 备份恢复 | clean-SHA `pg_dump` 1,046,636 bytes；新建恢复库后验证 72 张表，再删除恢复库，结果通过 |
| 总门禁 | clean-SHA 26/26 步通过，417.065 秒；OpenAPI 8/8、OpenSpec 54/54、secrets 695 文件、diff check 与隔离资源清理通过 |

clean-SHA 机器报告：`acceptance-clean-13243b4.json`；专项证据：`approval-audit-etl-clean-13243b4.json`、`approval-audit-http-clean-13243b4.json`、`http-performance-clean-13243b4.json`。工作树报告仍保留用于审计前后差异，但不替代 clean-SHA 结论。

OpenSpec delta 已完整同步到 9 个主规格，并归档为 `2026-08-14-complete-platform-approval-audit-center`；归档未使用跳过规格或跳过验证参数。

修复循环保留了 `acceptance-repair-loop-python310-failure.json`：首次总闸门在审批/审计 ETL 导入 `datetime.UTC` 时因实际 Python 3.10.11 失败；已恢复 3.10 兼容写法并在第二次总闸门关闭。该失败没有被删除或改写。

## 视觉证据

- `pc-desktop-approval-applications.png`：桌面申请列表、KPI、筛选和行内动作；
- `pc-desktop-published-definition-readonly.png`：已发布版本表单整体禁用且无保存按钮；
- `pc-desktop-audit-integrity.png`：审计筛选、`VERIFIED` 独立校验和 CSV 导出；
- `pc-tablet-approval-audit-readonly.png`：平板只读角色仅见定义与审计，无写入/导出控件；
- `pc-mobile-approval-retry.png`：移动 503 后可恢复、导航/筛选/表格使用局部滚动且无 body 横向溢出。

视觉人工复核还发现并修正了 `failed_count` 字段漂移；新增浏览器断言固定显示“失败 0”，避免只靠类型检查遗漏证据数字。

## 合成迁移边界

报告 `infra/local-staging/out/approval_audit_etl/approval_audit_etl.json` 的结论为 `CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA`。真实旧报销/请假/触达模板/操作日志仍为 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`；没有把合成行标记为生产对账或切换完成。

## 组合能力结论

20 项矩阵中的“组织/RBAC/园区范围/审批/审计”可升级为 `IMPLEMENTED_AND_VERIFIED`。统一工作台仍缺少全事件源、组件配置和规则/消息调度，继续为 `MISSING`；员工移动端、租户小程序、真实旧数据迁移和生产部署状态不变。

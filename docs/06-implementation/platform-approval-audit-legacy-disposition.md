# 平台审批与审计旧系统证据及处置

> 取证日期：2026-08-14（Asia/Shanghai）
> 旧证据根：`D:\重构python\kwzg-Java-main`
> 新纵切：`complete-platform-approval-audit-center`
> 原则：只替代可由证据证明的审批平台能力；旧 HR、报销、招商触达等领域本体仍由各自纵切负责，缺少旧 schema/脱敏数据时不得合成审批历史。

## 原始证据与裁决

| 旧能力 | 代码/页面/数据库证据 | 证据揭示的问题 | 新系统处置 |
| --- | --- | --- | --- |
| 报销申请/审核 | `reimbursement/ReimbursementController.java`、`Service.java`、`Repository.java`；PC/移动 `views/reimbursement/application/*`、`audit/*`；`magic.sql` 的 `reimbursement` | `status=0/1/2` 与一段 `auditOpinion` 直接覆盖；没有不可变定义版本、节点任务或决定事件链 | 平台提供版本化定义、申请、任务、决定和审计证据；报销业务字段/页面本体仍归 Finance/HR 后续纵切，不冒充已替代 |
| 请假审批 | `hrm/HrmController.java` 的 `/hrm/leaveapplication*`；`HrmRepository.java` 运行时探测 `status/audit_user/audit_user_id`；PC/移动 `views/hrm/leaveapplication/*` | 审批人与状态直接写在业务记录，字段名和类型依赖现场表结构 | 可映射到平台审批的候选规则已定义；真实转换保持 `BLOCKED`，直到获得授权 schema 和状态字典 |
| 招商触达模板/联系限制审核 | `investment/OutreachTemplate*`、`ContactRestrictionAuditQuery.java`、`RadarOperationAuditQuery.java` 及 `OutreachTemplateManagerDrawer.vue` | 多个领域各自维护审核状态，外部触达与合规边界不可由通用审批引擎猜测 | 平台引擎可承载显式定义；具体领域回调、企微/外呼真实联调继续保持未完成 |
| 菜单与工作台待办 | `MenuService.java` 注入报销/请假 PC 与移动路由；`DashboardOverview*` 汇总报销待审 | 待办来自散落状态查询，没有稳定任务身份、委托或 SLA | 新 `approval_tasks` 在节点打开时物化稳定候选，并一对一投影 `WorkItem`；工作台不是决定来源 |
| API/操作日志 | `magic.sql` 的 `api_log` 记录 method/path/用户/时间；各业务另有局部 audit 表 | 只能证明请求发生，不能证明业务决定未被篡改；日志还可能携带原始参数 | 新审计链对新记录做递增序列、前哈希和 SHA-256；详情递归脱敏、限长，旧行明确为 `LEGACY_UNVERIFIED` |

## 状态与字段映射

| 旧证据 | 新语义 | 转换规则 | 状态 |
| --- | --- | --- | --- |
| 报销 `status=0/1/2` | `PENDING/APPROVED/REJECTED` | 仅在责任人确认旧枚举且行级样本可对账后转换 | `BLOCKED_EXTERNAL` |
| 请假 `status`（现场类型不稳定） | 显式审批状态 | 未获得状态字典时进入隔离清单，不猜测 | `BLOCKED_EXTERNAL` |
| `auditOpinion` | 决定 `remark` | 可迁移文本，但不能据此伪造操作者、节点、时间或定义版本 | `READY_CONDITIONAL` |
| `audit_user/audit_user_id` | `actor_user_id` / 原审批人 | 必须通过同租户用户映射；无法解析时保留源引用并隔离 | `BLOCKED_EXTERNAL` |
| 业务记录只有终态、无历史 | `LEGACY_COMPAT` 申请 | 保留可证明终态；定义版本、任务和决定历史保持空，不补造 | `READY_CONDITIONAL` |
| `api_log` | `audit_logs` | 旧日志不回填哈希；新系统查询时显示 `LEGACY_UNVERIFIED` | `READY` |
| 手机、邮箱、token、password 等详情 | 脱敏/删除后的 `detail_json` | 密钥字段替换 `[REDACTED]`；手机号/邮箱按注册规则掩码；超限截断 | `IMPLEMENTED_AND_VERIFIED` |

## API 与用户入口处置

| 旧入口 | 新入口/处置 |
| --- | --- |
| `/api/reimbursement` 直接审核 | 领域先创建/绑定平台申请，再由 `/api/v1/approval-tasks/{id}/decide` 决定；通用接口继续禁止绕过 Lease 等领域状态机 |
| `/hrm/leaveapplication/{id}` 覆盖状态 | 待 HR 纵切提供显式领域回调；本次不删除旧业务差距 |
| 分散模板审核/限制释放 | 待 Investment/Compliance 回调落地；平台只提供可审计编排能力 |
| 无统一定义管理 | `/api/v1/approval-definitions*` 与 PC“流程定义”页，草稿可编辑、发布版本不可覆盖 |
| 无稳定审批任务 | `/api/v1/approval-tasks`、委托、SLA sweep 和 WorkItem 投影 |
| `api_log` 只能按请求看 | `/api/v1/audit-logs` 查询/详情/独立校验/受权 CSV 导出和 PC“审计中心” |

## 数据迁移门禁

合成 `kwzy.approval-audit.synthetic.v1` 已证明 dry-run、事务中断恢复、首次 apply、幂等重放、逐表对账和 fixture-only rollback；合成数据有 1 个发布版本、2 个节点、2 个申请、2 个任务、1 个委托、2 个源证据事件和 3 条哈希审计记录，重复执行插入均为 0，原始 PII/伪造决定均为 0，授权关系行前后完全一致。

以下外部证据仍缺失，真实迁移必须保持 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`：

- 经授权的报销、请假、触达模板、限制审核与操作日志 schema dump；
- 脱敏行样本、状态字典、审批人映射和时间字段可信度说明；
- 业务负责人签字的“终态可保留/历史不可证明”处置；
- 远程预发、停写窗口、增量同步、备份恢复和回切授权。

本纵切完成的是平台审批/审计能力，不代表 HR、报销、招商触达等旧领域页面和真实数据已经下线或迁移。

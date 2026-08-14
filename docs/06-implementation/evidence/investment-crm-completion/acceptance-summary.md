# 招商 CRM 全旅程补全验收摘要

> 日期：2026-08-14
> 分支：`feat/full-rebuild-completion`
> 范围：自动分配、第一类带看、版本化意向与统一审批门禁、签名渠道接收、旧数据合成迁移
> 结论：`IMPLEMENTED_AND_VERIFIED`（本地产品与适配器契约）；真实旧数据与真实渠道仍为外部阻塞

## 1. 实现边界

- 自动分配使用租户/园区范围内的版本化规则与成员容量，发布态决定创建、渠道和回收触发；无可用规则或成员时回落公海，不伪造负责人。
- 带看是独立主数据，覆盖排期、确认、改期、完成、取消、爽约、Unit 关联、时间冲突和乐观锁；完成只投影一条 `VISIT` 活动。
- 意向版本冻结单元、面积、价格、期限和校验和；权威状态来自统一 Approval Request。`PENDING/REJECTED/RETURNED/WITHDRAWN`、异线索和过期意向均不能锁房，只有未过期 `APPROVED` 版本允许锁定、续锁和转合同。
- 渠道使用 raw-body HMAC-SHA256、时间窗、恒定时间比较、事件唯一键、加密载荷、字段 allow-list、隔离与幂等重放。配置创建时保持 `NOT_CONNECTED`，首个本地有效签名事件后才变为 `LOCAL_CONTRACT_VERIFIED`。
- 真实 Radar/企微/外呼/短信厂商没有凭据或沙箱证据，继续 `NOT_CONNECTED/BLOCKED_EXTERNAL`；本验收没有发起外部网络请求。

## 2. 数据库与迁移

| 门禁 | 结果 |
| --- | --- |
| PostgreSQL | Docker `postgres:16`，仅 loopback 测试库 |
| Alembic | `heads == current == s5b13d8e0f97`，唯一 head |
| fresh / down-up | 空库 `upgrade head`、`downgrade -1`、再 `upgrade head` 均通过 |
| metadata parity | `alembic check`：`No new upgrade operations detected`；ORM 约束测试 4/4 |
| 合成 CRM ETL | 5/5；17 类目标对象，事务中断回滚、恢复、首次导入、零新增重跑、数量/孤儿/校验和/敏感列对账、schema rollback |
| 隔离 | `AMBIGUOUS_OWNER`、`INVALID_UNIT_REFERENCE`、`INFERRED_APPROVER`、`UNKNOWN_CHANNEL` 四类证据不足记录只保存指纹 |
| 备份恢复 | `pg_dump -Fc` 584,376 bytes；恢复到 `kwzy_crm_restore_test`，94 表与 Alembic `s5b13d8e0f97`；验证后删除恢复库 |
| dump SHA-256 | `fb1b6496119ffd52d8d869ed32067503f86773ea2a5fb4d4675cbb9a13fd066a`；临时 dump 已删除 |

真实生产/旧库 schema、脱敏样本和主键映射未获授权，因此数据迁移总状态仍是 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`，不能输出真实迁移 PASS。

## 3. 测试与运行证据

| 类别 | 结果 |
| --- | --- |
| 服务/API/OpenAPI/租户隔离/PG 并发/ETL 聚合 | 42 passed，0 failed，32.13 s |
| 招商闭环专项 | 4 passed；异线索、未批准、拒绝、退回、撤回、过期均 fail closed；规则成员园区授权撤销后从预演与执行排除并回落公海 |
| Playwright 招商文件 | 8 passed，0 failed；真实 PG16、FastAPI、production Vite build、真实 HTTP；移动 loading/空态/403/offline/重试/无溢出已自动断言 |
| 签名渠道专项 | 1 passed；创建 `NOT_CONNECTED` → 有效 HMAC 接收 → `LOCAL_CONTRACT_VERIFIED` → 同事件同 inbox/Lead |
| 前端 | `vue-tsc --noEmit` PASS；ESLint 0 warning；production build PASS |
| Ruff | 新文件全规则 PASS；全项目 `E9,F63,F7,F82` error gate PASS |
| OpenAPI | YAML strict 与运行时方法集合测试通过；公开签名路由在 JWT 外，管理/重放路由仍需权限 |

已分类的关键词扫描中，`placeholder` 只出现在真实表单提示；`demo` 只出现在合成 ETL 的 `tenant-demo` 值。招商实现无 TODO/FIXME/NotImplementedError/stub/mock/fake、本地 JSON 数据源或未挂载 router。

## 4. 性能、安全和可靠性

- 真实 HTTP：1,000 请求、并发 25、预热 40，覆盖 Lead 列表、漏斗摘要、阶段看板、分配规则和渠道列表。
- 结果：0 错误，p95 `256.359 ms`，吞吐 `156.018 req/s`；门槛 p95 ≤ 500 ms、错误率 ≤ 1%、吞吐 ≥ 20 req/s，PASS。
- PG 并发覆盖：规则双发布、带看双完成、签名事件重复/并发、Unit 锁竞争、过期锁重获、锁与合同激活互斥；均保持单一获胜、幂等或显式 409。
- 安全覆盖：数据库派生权限、敏感权限 fail closed、租户/园区 IDOR 404、严格额外字段 422、HMAC 篡改统一 401、原始密钥/电话不进入响应或日志、渠道载荷不能指定内部 owner/permission/approval/lock/contract。

性能机器报告：`http-performance-worktree.json`。

## 5. 浏览器与视觉

- 应用内浏览器独立检查桌面 `1440×1000`、平板 `820×1180`、移动 `390×844`；平板/移动页面级横向溢出均为 `false`，控制台 warning/error 为 0。
- 桌面详情真实显示 `COMPLETED` 带看、`APPROVED v1` 意向、审批深链、VISIT/跟进/转化时间线和已转合同状态。
- 治理页真实显示发布规则 `ACTIVE v1`、默认关闭 `NOT_CONNECTED` 渠道与本地已验签 `LOCAL_CONTRACT_VERIFIED` 渠道，没有静态假图表或假按钮。

截图：

- `pc-desktop-assignment-channel-governance.png`
- `pc-desktop-viewing-intent-conversion.png`
- `pc-tablet-crm-workspace.png`
- `pc-mobile-crm-workspace.png`

## 6. 剩余阻塞

- 经授权旧 schema dump、脱敏样本、旧用户/园区/审批/Unit/渠道字典和真实新旧对账：`BLOCKED`，责任人是数据负责人/DBA 与业务数据 Owner。
- 真实渠道沙箱协议、凭据、IP 白名单、回调证书和合规审批：`BLOCKED_EXTERNAL`，责任人是集成负责人/供应商/安全合规。
- AI 招商评分、企微/自动触达不在本纵切内，能力矩阵仍由 AI 与外部平台条目单独记为 `MISSING/BLOCKED`，没有借本地 HMAC 适配器宣称完成。
- 生产部署未获人工授权，未连接生产、未执行生产迁移、未合并 main。
- OpenSpec 任务 5.5 中的 `revoked` 与权威 delta spec 不一致：delta spec 只定义审批 `PENDING/APPROVED/REJECTED/RETURNED/WITHDRAWN`，而任务文字可被解释为“批准后撤销”。当前已验证规则成员园区授权撤销和审批撤回，但没有伪造不存在的 `ApprovalRequest.REVOKED`；该单项保持未关闭，待业务架构明确是复用 `WITHDRAWN`、新增撤销态，还是修正任务归属。

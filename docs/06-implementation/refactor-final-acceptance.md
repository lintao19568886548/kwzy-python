# 瞰维智管 V2 重建验收状态

> 更新时间：2026-08-13 19:50（Asia/Shanghai）
> 结论：**资产/租控与招商 CRM V2 本次定义范围在精确提交上验收通过；V2 全量重建未完成。**
> 本文撤销把旧 Java 代码级替代、全前端替代或全系统重建写成 COMPLETE 的历史表述。

## 1. 已验证提交与复现证据

| 项 | 值 |
| --- | --- |
| 分支 | `main` |
| 被测 HEAD | `8adcd77e782db47a466ba0759ac04ffaae488b1b` |
| 被测时远程 | `origin/main=d257c1b1c10cc246eb0dc006af609163826a53c8`；被测代码当时为本地 ahead 1，待证据提交后一起非强推送 |
| 被测时工作树 | clean |
| Alembic 唯一 head | `j6e24f9a1c08` |
| 验收脚本 | `infra/local-staging/run_full_acceptance.ps1` |
| 脚本 SHA256 | `747C954458394D6D9F8CE4B9355DB849C3859A2199C7090386334311D3887EC3` |
| 机器报告 | `infra/local-staging/out/acceptance_20260813_195020.json`（gitignored，本机） |
| 开始/结束 | 2026-08-13 19:45:07 / 19:50:20 +08:00 |
| 总耗时 | 313740 ms（约 5m14s） |
| 总结果 | 21 steps / 21 exit 0 |

## 2. 已通过的本地门禁

| 门禁 | 结果 |
| --- | --- |
| PostgreSQL 16 fresh upgrade | base → `j6e24f9a1c08 (head)` PASS |
| downgrade/upgrade | head → -1 → head PASS |
| 后端测试 | 166 passed，1 个依赖弃用 warning；含资产竞态、CRM 权限/事务回滚/公海认领/锁房与 Lease 激活串行化 PG 测试 |
| fixture ETL fast | PASS |
| fixture ETL acceptance | PASS；64244 OK、1 个预置脏行隔离、PG reconcile=true |
| Identity ETL | 合成 users/roles/menus/user-role/role-menu/role-park：dry/apply/idempotency/reconcile/rollback PASS |
| Asset ETL | 合成 4 nodes/4 units/2 lineages；首次导入、幂等复跑、面积 280/180/40、零孤儿/重复及 rollback PASS |
| CRM ETL | 合成 5 leads/4 activities/4 assignments/1 merge/1 PII quarantine；dry/apply/idempotent/reconcile/rollback PASS，原始 PII 未落库 |
| 备份恢复 | PASS；dump 883310 bytes；恢复 52 tables |
| 前端静态质量 | ESLint PASS；vue-tsc PASS；production build PASS |
| 前端单测 | 4 passed / 2 files |
| 浏览器 E2E | 32 passed / 0 failed / 0 skipped；CRM 6 条覆盖主链、公海、管理分配/合并、只读、409/503 恢复、平板键盘检查 |
| OpenAPI | 4 runtime/YAML contract tests PASS；YAML strict PASS；CRM V2 20 个路径方法有精确约束 |
| OpenSpec | 38 passed / 0 failed |
| secrets scan | PASS；545 tracked/untracked non-ignored files |
| 资源清理 | 专用 PG16 容器/网络/卷清理 PASS；不再误杀 8000 无关服务 |

以上证据只证明当前已挂载的核心纵切；不能证明未实现模块、员工移动端、租户小程序或真实外部平台。

本轮机器验收精确绑定 CRM 实现提交 `8adcd77`；其后的总控证据、任务勾选和 OpenSpec 同步归档不改动被测业务代码。资产变更此前已同步归档；CRM 变更将在本证据提交后同步主规格并归档。

## 3. 当前可验收范围

- Identity：密码登录、cookie/body refresh、重放与即时吊销、登录限流、安全事件、页面二次验证、用户/角色/权限/菜单/园区授权、组织字典参数管理；短信登录、租户开通等旧长尾仍未替代。
- Park/Space/Unit：Park→AREA/BUILDING/FLOOR 空间树，父子/同园区/编码/循环/依赖规则；出租单元 current-only 版本、乐观锁、结构变更、拆并血缘与 Lease 占用联动。
- Rent Control：服务端统一筛选与面积/出租率口径；PC 摘要、矩阵/列表、空间/单元编辑、Lease/Party/版本/血缘/工单详情、权限和异常状态。
- Party：主档、联系人、地址、角色、园区关系、风险事件。
- Lease/Bill/Payment：基础状态机、占用、出账、部分/全额核销、冲正、幂等与 PG 并发测试。
- Investment CRM：规范化去重/覆盖/合并、活动时间线、状态机、分配/改派/公海认领释放/超时回收、漏斗、可解释匹配、限时锁房和原子转 Party/Lease；外部获客与自动触达明确不在本地完成范围。
- Workbench/Work orders/Collection：基础待办、简版工单和催缴案件主链。
- Attachments/Approvals/Integrations：最小适配；外部短信/通知/存储为本地 fake/local，明确 `NOT_LIVE`。
- PC：13 个鉴权业务页 + login/forbidden；32 条浏览器主链。

## 4. 阻止全产品 PASS 的事实

1. 员工移动端与租户微信小程序均不存在。
2. 资产/租控已闭合空间树、单元版本/拆并及矩阵/列表，但集团实体、GIS/CAD/BIM 地图、组合经营分析和真实旧资产数据演练仍未完成。
3. 招商内部 CRM 本次定义范围已闭合，但真实渠道/radar/企微接入、自动触达、复杂标签画像、意向审批/签署衔接、AI 评分推荐和真实旧数据演练仍缺失。
4. 合同缺多单元/复杂费用、变更单与补充协议版本链、签章印章、履约/退租/违约闭环。
5. 账单/收款缺自动计费、抄表、银行/支付到账识别、待匹配池、多账单核销、争议和审批化催缴。
6. 工单缺多入口、技能班次负荷派单、SLA、转派暂停返工重开、报价/材料/工时/租户确认。
7. 设备、巡检、安防、IoT、HR、供应商/采购/库存、政策活动公告和资源预约尚未实现。
8. 经营驾驶舱和多角色工作台只有窄摘要；`analytics` 仍为未挂载空响应。
9. `ai_assist` 是未挂载明确 stub，尚无可审计、需确认、可降级的 AI 能力层。
10. ETL 只跑合成 fixture；未取得经授权的脱敏旧数据，未做新旧业务结果全量对账、增量同步和切换演练。
11. 无真实第三方凭据、远程预发环境和生产授权；外部联调、性能验收、监控告警/容灾运维尚未完成。

## 5. 外部平台状态

| 平台组 | 当前状态 | 原因/下一门禁 |
| --- | --- | --- |
| SMS/微信/邮件/对象存储 | `ADAPTER_NOT_LIVE` | fake/local 与 fail-closed 已测；缺真实凭据和供应商验收 |
| 银行/聚合支付/微信支付宝 | `NOT_LIVE` | 缺商户/银行沙箱资料、回调域名和验签密钥 |
| 发票/税务/财务软件 | `NOT_LIVE` | 未选厂商/无凭据 |
| OCR/电子签章/存证/档案 | `NOT_LIVE` | 未选厂商/无凭据 |
| 门禁/停车/视频/消防/能耗/IoT | `NOT_LIVE` | 未取得协议、设备模拟样本或厂商资料 |
| OA/ERP/HR/采购/协作平台 | `NOT_LIVE` | 未确认目标平台与契约 |
| 云模型/私有模型 | `NOT_LIVE` | AI 业务网关尚未实现；无模型凭据 |

## 6. 当前验收结论

```text
KWZY_PRODUCT_BLUEPRINT=IN_PROGRESS
KWZY_BACKEND_REBUILD=CONDITIONAL_CORE_SLICE_ONLY
KWZY_PC_UI_REBUILD=CONDITIONAL_CORE_SLICE_ONLY
KWZY_EMPLOYEE_MOBILE=BLOCKED_NOT_IMPLEMENTED
KWZY_TENANT_MINIPROGRAM=BLOCKED_NOT_IMPLEMENTED
KWZY_LEGACY_CAPABILITY_CLOSURE=BLOCKED
KWZY_DATA_MIGRATION_REHEARSAL=CONDITIONAL_FIXTURE_ONLY
KWZY_SECURITY_ACCEPTANCE=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_PERFORMANCE_ACCEPTANCE=BLOCKED_NOT_RUN
KWZY_E2E_ACCEPTANCE=CONDITIONAL_CORE_SLICE_ONLY
KWZY_OPERATIONS_READINESS=BLOCKED
KWZY_FULL_REBUILD_ACCEPTANCE=BLOCKED
KWZY_PRODUCTION_DEPLOYMENT=AWAITING_HUMAN_APPROVAL
```

验收脚本的原始结尾标识同样保持真实：`KWZY_IMPLEMENTED_SCOPE_LOCAL_ACCEPTANCE=PASS`、`KWZY_PC_CORE_SLICE_ACCEPTANCE=PASS`、`KWZY_FULL_FRONTEND_REPLACEMENT=BLOCKED_MOBILE_AND_MINIPROGRAM_NOT_IMPLEMENTED`。

这些状态会随每个业务纵切的真实证据更新。只有 `full-rebuild-traceability-matrix.md` 无未处置能力、三端关键旅程全绿、脱敏真实迁移/安全/性能/运维门禁全部成立时，才可输出最终 PASS。

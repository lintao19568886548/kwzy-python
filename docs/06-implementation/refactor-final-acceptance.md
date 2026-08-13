# 瞰维智管 V2 重建验收状态

> 更新时间：2026-08-13 17:00（Asia/Shanghai）
> 结论：**稳定核心样板纵切本地验收通过；Identity 候选功能门禁通过、最终整套报告待复跑；V2 全量重建未完成。**
> 本文撤销把旧 Java 代码级替代、全前端替代或全系统重建写成 COMPLETE 的历史表述。

## 1. 已验证提交与复现证据

| 项 | 值 |
| --- | --- |
| 分支 | `main` |
| 被测 HEAD | `d9c0b0b1a35a3a25dd205d765ef2e7f36e5c74e6` |
| 被测时远程 | `HEAD == origin/main` |
| 被测时工作树 | clean |
| Identity 候选 Alembic head | `h4c02d7e9a86` |
| 验收脚本 | `infra/local-staging/run_full_acceptance.ps1` |
| 脚本 SHA256 | `BBA0FE42D41F59AFE8D5D98BC3FA8FBE07358688799D9C20E29AB2AA476BE27C` |
| 机器报告 | `infra/local-staging/out/acceptance_20260813_160036.json`（gitignored，本机） |
| 开始/结束 | 2026-08-13 15:55:31 / 16:00:36 +08:00 |
| 总耗时 | 305170 ms（约 5m05s） |
| 稳定基线总结果 | 18 steps / 18 exit 0 |
| Identity 候选报告 | `acceptance_20260813_165323.json`：143 pytest、25 Playwright 等功能门禁通过；仅 `git diff --check` 因本总控文档行尾失败 |

## 2. 已通过的本地门禁

| 门禁 | 结果 |
| --- | --- |
| PostgreSQL 16 fresh upgrade | base → `h4c02d7e9a86 (head)` PASS（Identity 候选） |
| downgrade/upgrade | head → -1 → head PASS |
| 后端测试 | 143 passed，1 个依赖弃用 warning（Identity 候选） |
| fixture ETL fast | PASS |
| fixture ETL acceptance | PASS；64244 OK、1 个预置脏行隔离、PG reconcile=true |
| Identity ETL | 合成 users/roles/menus/user-role/role-menu/role-park：dry/apply/idempotency/reconcile/rollback PASS |
| 备份恢复 | PASS；dump 838139 bytes；恢复 47 tables（Identity 候选） |
| 前端静态质量 | ESLint PASS；vue-tsc PASS；production build PASS |
| 前端单测 | 4 passed / 2 files |
| 浏览器 E2E | 25 passed / 0 failed / 0 skipped；含跨租户、cookie/session、System Admin 与严格 fake SMS/outbox |
| OpenAPI | 3 contract tests PASS；YAML strict PASS；运行时 87 paths / 122 operations |
| OpenSpec | 32 passed / 0 failed（Identity 候选；本文更新后再次复跑） |
| secrets scan | PASS；483 tracked files |
| 资源清理 | 专用 PG16 容器/网络/卷清理 PASS；不再误杀 8000 无关服务 |

以上证据只证明当前已挂载的核心纵切；不能证明未实现模块、员工移动端、租户小程序或真实外部平台。

## 3. 当前可验收范围

- Identity：密码登录、cookie/body refresh、重放与即时吊销、登录限流、安全事件、页面二次验证、用户/角色/权限/菜单/园区授权、组织字典参数管理；短信登录、租户开通等旧长尾仍未替代。
- Park/Unit：基础园区与扁平出租单元 CRUD/状态。
- Party：主档、联系人、地址、角色、园区关系、风险事件。
- Lease/Bill/Payment：基础状态机、占用、出账、部分/全额核销、冲正、幂等与 PG 并发测试。
- Workbench/Leads/Work orders/Collection：基础待办、线索、简版工单和催缴案件主链。
- Attachments/Approvals/Integrations：最小适配；外部短信/通知/存储为本地 fake/local，明确 `NOT_LIVE`。
- PC：12 个鉴权业务页 + login/forbidden；24 条浏览器主链。

## 4. 阻止全产品 PASS 的事实

1. 员工移动端与租户微信小程序均不存在。
2. 资产/租控没有组织空间层级模板、出租单元拆并和有效期版本链，也没有矩阵/地图/分析多视图。
3. 招商缺规则分配、公海、超时升级、完整跟进状态机、审批锁房、并发防重、AI 匹配和完整漏斗。
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

这些状态会随每个业务纵切的真实证据更新。只有 `full-rebuild-traceability-matrix.md` 无未处置能力、三端关键旅程全绿、脱敏真实迁移/安全/性能/运维门禁全部成立时，才可输出最终 PASS。

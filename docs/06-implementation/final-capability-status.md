# 最终能力状态（代码级）

生成于 main closeout 批次。

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| Identity 会话/用户/角色/菜单 | IMPLEMENTED | tests identity |
| 组织/字典/参数 | IMPLEMENTED | test_system_config_api |
| Party/Lease/Bill/Payment | IMPLEMENTED | test_main_chain_e2e |
| Workbench/WorkItem | IMPLEMENTED | test_work_item_api |
| Investment Leads | IMPLEMENTED | test_lead_api + main chain |
| Work Orders | IMPLEMENTED | test_work_order_api |
| Collection Cases | IMPLEMENTED | test_collection_case_api |
| Approvals（含撤回/历史） | ADAPTER_COMPLETE | test_approval_api |
| Attachments local | ADAPTER_COMPLETE | test_attachments_api |
| SMS/Notify/WeChat providers | ADAPTER_COMPLETE | test_providers + runbook |
| OSS S3 production stub | ADAPTER_COMPLETE | S3FileStorage fail-closed |
| Radar 爬虫 | DEPRECATED_WITH_EVIDENCE | java disposition |
| HRM/宿舍 | DEPRECATED_WITH_EVIDENCE | 范围外 |
| 支付网关/企微/OCR 真联调 | LIVE_VERIFICATION_PENDING | 需凭据 |
| ETL fixture→PG16 | READY_FOR_STAGING_DATA | apply_to_postgres + large fixture |
| 前端主链 UI | REDESIGNED | apps/web build+e2e |
| 浏览器完整旅程 | PARTIAL | e2e main-chain 需 API |

`LIVE_EXTERNAL_INTEGRATION=NOT_VERIFIED`

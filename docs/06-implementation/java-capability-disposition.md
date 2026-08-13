# 旧 Java 能力处置清单（持续闭合，禁止 UNKNOWN）

> 更新：2026-08-13  
> 证据根：`D:\重构python\kwzg-Java-main`（只读）  
> 策略枚举：`RETAIN | REDESIGN | ADAPTER | DEPRECATE | DEFER`

| 旧能力域 | 证据位置 | 策略 | 新系统落点 | 状态 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 登录/会话/RBAC | backend auth | REDESIGN | identity | PARTIAL | token_version/refresh 有；组织/字典/参数本批补齐 |
| 园区/单元 | park modules | REDESIGN | park_property | PARTIAL | 主链可用 |
| 客户/主体 | customer | REDESIGN | party | COMPLETE(v1) | PERSON 地址拒绝 |
| 合同 | rental contract | REDESIGN | lease | COMPLETE(v1) | 押金流水 DEFER |
| 账单 | bill | REDESIGN | billing | COMPLETE(v1) | 滞纳金/表计 DEFER |
| 收款 | payment | REDESIGN | collection payment | COMPLETE(v1) | 在线支付 DEFER |
| 催缴案件 | collection | REDESIGN | collection_cases | PARTIAL | 最小案件；SMS DEFER |
| 工作台待办 | dashboard | INNOVATION/REDESIGN | workbench | PARTIAL | 事件挂接进行中 |
| 招商线索 | investment | REDESIGN | leads | PARTIAL | 雷达/企微 DEFER |
| 运维工单 | maintenance | REDESIGN | work_orders | PARTIAL | 巡检资产拆分 DEFER |
| 审批流 | workflow | DEFER | — | DEFER | 无统一新模型；需产品选型 |
| 通知/短信 | sms | DEFER | system_params 预留 | DEFER | 外部密钥不入库明文 |
| 附件/文件 | file | DEFER | — | DEFER | 对象存储未选 |
| 导入导出 | import | DEFER | ETL tools | PARTIAL | 骨架 dry-run |
| 报表/看板 | analytics | REDESIGN | workbench summary | PARTIAL | 复杂图表 DEFER |
| AI 识别 | ai-bill | DEFER | ai_assist stub | DEFER | 仅草稿策略保留 |
| 小程序/App | playground mobile | DEFER | apps/web 桌面优先 | DEFER | 非一期门禁 |
| 雷达获客 | radar | DEPRECATE/DEFER | — | DEFER | 爬虫合规风险；不默认保留 |
| 在线收银台 | pay gateway | DEFER | — | DEFER | 二期 |

**UNKNOWN 计数：0**（未扫细节的子能力并入上表 DEFER 行，并要求后续 change 拆解，不得静默消失）。

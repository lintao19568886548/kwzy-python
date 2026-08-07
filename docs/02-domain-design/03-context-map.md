# 上下文映射与集成设计

---

## 1. 上下文关系图

```text
                    [IdentityAccess]
                           │ 认证/鉴权 ACL
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    [TenantOps]     [ParkProperty]    （所有业务模块）
          │                │
          │                │ park_id / unit_id
          │                ▼
    [Investment] ──LeadConverted──▶ [Lease]
    [CRMChannel] ──qualified──▶ [Investment]
          │                        │
          │                        │ contract_id / party_id
          │                        ▼
    [Metering] ──ReadingCaptured──▶ [Billing] ◀── [AIAssist] BillDraft
                                       │
                                       │ BillIssued / Overdue
                                       ▼
                                 [Collection] ──PaymentReceived──▶ [FinanceLedger]
                                       │
                                       └──▶ [Notification]（短信/站内信）

    [FacilityOps] [HRM] [AccessControl] ── 相对独立，共享 Park + Identity

    [Analytics] ◀── 只读订阅事件/定时同步（反腐败层读模型）
```

---

## 2. 集成模式

| 关系 | 模式 | 说明 |
| --- | --- | --- |
| Identity → 各模块 | **ACL（防腐）** | 只暴露 `CurrentUser`、`require_perm`、`ParkScope` |
| Lease → ParkProperty | **客户-供应商** | Lease 调 ParkProperty 应用服务占用单元 |
| Investment → Lease | **领域事件** | 转化不直接插合同表 |
| Metering → Billing | **领域事件** | 松耦合 |
| AIAssist → Billing | **开放主机服务** | 提交 Draft DTO，Billing 校验后落库 |
| Billing → Collection | **客户-供应商 + 事件** | 出账后 Collection 可查 Bill 读模型 |
| Collection → Finance | **领域事件** | 统一入账 |
| Analytics → 各上下文 | **遵奉者/单独模型** | 禁止直查乱写 |

---

## 3. 防腐层 DTO（跨上下文）

### 3.1 LeadConverted

```json
{
  "event_id": "uuid",
  "tenant_id": 1,
  "lead_id": 100,
  "park_id": 2,
  "party_name": "某某科技有限公司",
  "contact_phone": "13800000000",
  "intent_area": 1200,
  "preferred_unit_ids": [11, 12],
  "owner_user_id": 5,
  "occurred_at": "2026-08-06T10:00:00+08:00"
}
```

### 3.2 BillDraft（AI/导入）

```json
{
  "park_id": 2,
  "party_name": "某某科技",
  "party_id": null,
  "contract_id": null,
  "period_start": "2026-07-01",
  "period_end": "2026-07-31",
  "due_date": "2026-08-10",
  "source": "AI",
  "source_ref": "job_33",
  "confidence": 0.91,
  "lines": [
    {
      "fee_code": "ELECTRIC",
      "description": "电表-A",
      "quantity": 1200,
      "unit_price": 0.85,
      "amount": 1020.0,
      "meter_reading_from": 10000,
      "meter_reading_to": 11200,
      "multiplier": 1
    }
  ]
}
```

### 3.3 PaymentReceived

```json
{
  "payment_id": 50,
  "tenant_id": 1,
  "park_id": 2,
  "party_id": 9,
  "amount": 50000,
  "paid_at": "2026-08-06T15:00:00+08:00",
  "allocations": [{"bill_id": 70, "amount": 50000}]
}
```

---

## 4. 同步 vs 异步

| 交互 | 方式 | 原因 |
| --- | --- | --- |
| 登录鉴权 | 同步 | 请求路径 |
| 占用单元 | 同步本地事务 | 强一致 |
| 出账 | 同步 | 用户等待结果 |
| 导入/AI 识别 | 异步 Job | 耗时长 |
| 短信催缴 | 同步受理 + 异步发送 | 体验与通道 |
| 财务入账 | 同步写 outbox + 异步投影 或 同事务写 ledger | 一期可同事务 |
| 雷达爬虫 | 独立 worker | 隔离负载 |
| 分析指标 | 定时/事件投影 | 不拖交易 |

---

## 5. 模块依赖规则（代码层强制）

允许：

```text
api → service → domain
service → repository
service → 其他模块的 public service / events（单向）
```

禁止：

```text
billing.repository 直接 join investment 表乱改
ai_assist 直接 update bills set status=PAID
modules 循环 import
```

公共内核 `app/shared`、`app/core` 只放：

- 配置、DB session、安全、异常、分页、outbox 基础设施
- 不放业务实体

---

## 6. 外部系统端口

| 端口 | 实现适配器 | 上下文 |
| --- | --- | --- |
| SmsSender | 联麓等 | Collection / Identity |
| LlmClient | 百炼/其他 | AIAssist |
| MeterVendor | 合众/亿玛 | Metering |
| PaymentGateway | 微信/支付宝 | Collection（二期租户缴费） |
| WecomClient | 企业微信 | CRMChannel |
| ObjectStorage | 本地/OSS | shared |

---

## 7. 读模型建议

| 读模型 | 用途 | 构建 |
| --- | --- | --- |
| workbench_todos | 工作台待办 | 定时 + 事件 |
| park_dashboard_stats | 园区看板 | 定时聚合表 |
| contract_expiry_list | 到期合同 | SQL 视图或任务 |
| ar_aging | 应收账龄 | 每日任务 |

Analytics 上下文只读这些表/视图，避免复杂实时多表 join 打爆主库。

---

## 8. 演进与拆服务触发条件

| 信号 | 动作 |
| --- | --- |
| 导入任务 CPU/内存冲高 | 拆 `import-worker` |
| 爬虫代理/封禁问题多 | 拆 `radar-worker` |
| 看板查询拖慢 API | 拆 `analytics-api` + 只读副本 |
| 多团队并行发布冲突 | 按上下文拆服务 |

一期保持 **模块化单体**，用目录与接口边界模拟微服务。

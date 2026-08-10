# Party API 草案 v1.3（终局）

> 设计 only。envelope、snake_case、`/api/v1`、Bearer JWT。  
> 生产数据方言：PostgreSQL 16（ADR-003d）。

---

## 1. 安全与权限

| 权限码 | 含义 |
| --- | --- |
| `party:read` | 读 park-scope 可见 Party；**默认不含完整风险原因** |
| `party:write` | 主档/角色/关系/联系人/archive/restore |
| `party:manage_unscoped` | 零园区关联 Party |
| **`party:risk_read`** | 读 `risk-events` 与完整 reason |
| **`party:risk_manage`** | blacklist / remove-blacklist |
| `*` | 全部动作；不绕过 park DataScope |

OpenAPI security：为 risk 端点单独标注 `party:risk_read` / `party:risk_manage`。

---

## 2. Party 主资源

| 方法 | 路径 |
| --- | --- |
| GET/POST | `/parties` |
| GET/PATCH | `/parties/{party_id}` |
| POST | `/parties/{party_id}/archive` |
| POST | `/parties/{party_id}/restore` |

**禁止：** 物理 DELETE；**禁止** PATCH 直接改 `risk_status`。

列表默认排除 ARCHIVED；`include_archived` / `status=ARCHIVED`。  
**无证件号字段。**

---

## 3. 风险 API（专用动作，非 PATCH）

| 方法 | 路径 | 权限 |
| --- | --- | --- |
| GET | `/parties/{party_id}/risk-events` | `party:risk_read` |
| POST | `/parties/{party_id}/blacklist` | `party:risk_manage` |
| POST | `/parties/{party_id}/remove-blacklist` | `party:risk_manage` |

### blacklist body

```json
{ "reason": "必填原因" }
```

### remove-blacklist body

```json
{ "reason": "必填解除原因" }
```

同事务：

1. 更新 `parties.risk_status` 与便捷 blacklist 字段  
2. **INSERT** `party_risk_events`（不可变）  
3. **INSERT** `audit_logs`  

restore ARCHIVED **不**自动 unblacklist。

---

## 4. 角色 / 园区关系 / 联系人

- 角色：`/parties/{id}/roles`  
- 园关系：`/parties/{id}/park-relations`，body 含 `park_id` + `party_role_id`  
- 联系人：嵌套 REST + 软删  

（规则同前轮，略。）

---

## 5. 错误码（风险相关增补）

| code | 场景 |
| --- | --- |
| PARTY_RISK_REASON_REQUIRED | 缺少 reason |
| PARTY_RISK_INVALID | 非法状态迁移（如已黑名单再黑） |
| PERMISSION_DENIED | 缺 risk_read / risk_manage |
| … | 见前轮 credit/relation 错误码 |

---

## 6. 旧接口兼容

| 项 | 值 |
| --- | --- |
| 旧路径 | `/rental/tenant*` |
| 新路径 | `/api/v1/parties*` |
| **removal_target_version** | **v2.0.0** |
| **removal_gate_status** | **NOT_READY** |

门禁（全部满足后才可独立 change 删除；到 v2.0.0 仍可因未满足而保留兼容层）：

1. deprecated 公告 ≥90 天  
2. 调用方全部登记  
3. PC/App/小程序/外部集成均已迁移  
4. 连续 30 天调用量 = 0  
5. 新 Party 接口稳定 ≥2 个正式发布周期  
6. 字段映射与迁移说明已发布  
7. 生产回归通过  
8. 人工下线批准  
9. 独立 OpenSpec change  
10. 任一条件不满足 → **继续保留**  

弃用期：Deprecation + Sunset 计划信息；调用量/调用方/request_id/路径；不记密码 Token 敏感体；禁止 301/302 写；适配层调 Party Application Service；不扩展 rental_tenant。

---

## 7. OpenAPI 同步（实现前）

- security schemes 含 risk 权限  
- risk-events / blacklist / remove-blacklist  
- 去掉主档 park_id；无证件字段  
- 文档注明 PG 16 生产 / SQLite 单测  

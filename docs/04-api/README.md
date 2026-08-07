# API 设计

| 文件 | 说明 |
| --- | --- |
| [openapi-v1-core.yaml](./openapi-v1-core.yaml) | 主链 OpenAPI **v1.1**（05.1 修订） |

## v1.1 要点

- 路径/字段 **snake_case**（`park_id` 等）
- 响应 **`{code, message, data}`** + `ErrorResponse`
- Bill：`status` 无 OVERDUE；返回 `is_overdue` / `open_amount`
- Payment：收款登记语义
- 补齐：Party GET/PATCH、Building 详情/改/删、page-access、logout/codes
- 催缴闭环：`/collection/cases` + `/{case_id}/records`
- 收款登记：`POST /payments` + `allocations` 分摊核销
- 写操作：`Idempotency-Key` 头参数

实现时以本文件与领域 ADR 为准，旧 Java 路径不作为契约。

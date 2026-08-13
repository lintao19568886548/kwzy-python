# 重构决策日志

## 2026-08-12

### D-001 Identity 实现策略

- **决策**：在现有单库租户模型上扩展 Identity，不复制旧 Java 中心库+多租户库切库。
- **理由**：Python 基线已是 shared-tenant 表隔离；完整中心库映射放入 ETL 后续阶段。
- **影响**：Refresh Token / 用户 / 角色 / 菜单均带 `tenant_id`。

### D-002 V2.3.2 证据

- **决策**：V2.3.2 证据包放在 `kwzy-python-review-artifacts`，不阻塞实现分支启动。
- **理由**：证据已 READY_FOR_HUMAN_REVIEW；实现并行推进，apply 用 `implement-identity-system-admin`。

### D-003 菜单模型

- **决策**：新 `menus` / `role_menus` 表承载动态菜单，不强制 1:1 复刻旧 menu 模板同步。
- **兼容**：后续可做旧 menu_id 映射表。

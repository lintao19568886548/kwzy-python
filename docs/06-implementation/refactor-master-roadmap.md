# KWZY 全系统重构主路线图

## 主线

```text
仓库基线
→ docs 业务蓝图追踪
→ V2.3.2 证据门禁（已完成于 artifacts）
→ Identity/System/Admin 实现（当前）
→ Party/Lease/Bill/Payment 复核
→ 剩余 Java 领域重构
→ 前端创新式重构
→ 数据迁移工具链
→ 全量测试与安全验收
→ main 合并
→ 最终验收包（生产迁移/部署仍 NOT_EXECUTED）
```

## 状态

| 阶段 | 状态 |
| --- | --- |
| Phase06 Party/Lease/Bill/Payment | COMPLETE（scoped，main） |
| V2.3.2 Identity 证据 | READY_FOR_HUMAN_REVIEW（artifacts） |
| Identity 实现 | IN_PROGRESS |
| 前端替换 | NOT_COMPLETE |
| 数据迁移工具 | NOT_COMPLETE |
| 生产部署 | NOT_EXECUTED |

## 创新原则

- 保留业务能力与不变量，不照搬 Java 实现
- 配置化规则、自动待办、工作台优先
- AI 仅建议，不绕过权限/财务

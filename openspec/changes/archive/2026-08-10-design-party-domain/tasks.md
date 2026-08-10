## 1. 终局三项决策

- [x] 1.1 生产 PostgreSQL 16；SQLite 开发/单测；ADR-003d
- [x] 1.2 首版 party_risk_events + party:risk_read/risk_manage；ADR-003e
- [x] 1.3 旧接口目标 v2.0.0、gate NOT_READY；ADR-003f
- [x] 1.4 结构性 Open Questions 清空；非阻塞参数单列

## 2. 文档与 OpenSpec 同步

- [x] 2.1 领域设计 + 决策追踪表 + 测试矩阵
- [x] 2.2 DDL 草案（PG 权威 + risk_events）
- [x] 2.3 API 草案（风险 API/权限/下线）
- [x] 2.4 实施计划 + implement 名称建议
- [x] 2.5 proposal/design/specs/tasks（含 party-persistence-dialect）

## 3. 校验

- [x] 3.1 openspec validate design-party-domain --strict
- [x] 3.2 输出 PHASE06-PARTY-DESIGN-FINAL-APPROVAL-READY
- [ ] 3.3 最终人工批准（等待）
- [ ] 3.4 批准后另开 implement-party-master（等待，本阶段不创建）

## 4. 禁止项

- [x] 4.1 不 apply / 不编码 / 不迁移
- [x] 4.2 不创建 implement change
- [x] 4.3 不 commit / push / archive

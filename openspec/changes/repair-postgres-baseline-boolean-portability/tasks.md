## Tasks

- [x] 1.1 确认失败 SQL 与非生产证据
- [x] 1.2 创建 OpenSpec repair change 并 strict validate
- [x] 1.3 最小修正 9f17fd2e9180 布尔赋值
- [x] 1.4 PG16 fresh upgrade + current==head
- [x] 1.5 PG downgrade/upgrade 往返
- [x] 1.6 临时 SQLite base→head
- [x] 1.7 pytest -m pg + SQLite 全量
- [x] 1.8 停止测试容器；敏感文件检查
- [x] 1.9 更新 runbook（脱敏）

## 禁止

- [x] 不 apply implement-party-master
- [x] 不写 Party 业务/ORM/迁移表
- [x] 本轮不 commit/push（按用户禁止）

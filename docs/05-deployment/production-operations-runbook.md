# 瞰维智管 V2 生产运维 Runbook（待授权模板）

> 本 Runbook 是可执行交付模板，不是生产部署或生产演练证明。当前产品能力与真实旧库迁移仍有阻塞，任何生产命令均须变更单、DBA 与业务负责人书面授权。

## 1. 不可绕过的门禁

1. 使用不可变镜像 SHA，禁止 `latest`；镜像需完成漏洞/许可证扫描和签名验证。
2. PostgreSQL 必须为 16.x；先在由 DBA 创建的隔离预发库执行 `alembic upgrade head`、`current == heads`、`downgrade -1 → upgrade head`、备份恢复和真实脱敏数据对账。
3. 密钥只从密钥管理器注入；不得把 `.env.production`、数据库导出、Token 或 PII 提交仓库。
4. `APP_ENV=production`、显式 Host/CORS、PostgreSQL URL、强 JWT、生产短信/微信和 S3 配置均由应用 fail-closed 校验。
5. 生产写入、切换 DNS、旧库停写、不可逆迁移和回滚必须单独人工授权。本仓库脚本不会自动连接生产。

## 2. 构建与离线验证

```powershell
docker build -f infra/production/api.Dockerfile -t registry/kwzy-api:<git-sha> .
docker build -f infra/production/web.Dockerfile -t registry/kwzy-web:<git-sha> .
docker compose -f infra/production/compose.production.example.yaml config -q
pwsh infra/local-staging/run_full_acceptance.ps1
```

验收脚本必须生成：Alembic、全量后端、前端、真实浏览器、合成 ETL、备份恢复、OpenAPI/OpenSpec、秘密扫描与真实 HTTP 性能报告。性能本地基线为 1000 个请求、并发 25、p95 ≤ 500 ms、错误率 ≤ 1%、吞吐 ≥ 20 req/s；这不是生产容量承诺。

## 3. 预发部署顺序

1. 记录数据库当前 revision、镜像 SHA、配置版本和备份对象不可变校验和。
2. 以只读凭据验证网络/DNS/证书，再由 DBA 执行备份并做可恢复性抽查。
3. 人工执行一次性迁移容器：

   ```powershell
   docker compose --profile operations -f infra/production/compose.production.example.yaml run --rm migrate
   ```

4. 验证 `alembic current` 唯一等于 `alembic heads`，再启动 API/Web；`/health/ready` 未返回 200 时不得接流量。
5. 先放 1% 流量，依次升至 10%、50%、100%；每阶段观察至少 15 分钟并完成角色冒烟和账务/合同/租控原始记录对账。

## 4. 监控目标与告警契约

以下是待预发/生产平台接入并验证的目标，不代表当前已达到：

| 信号 | 目标/告警 |
|---|---|
| API 可用性 | 月度目标 99.9%；5 分钟 5xx > 1% 告警 |
| API 延迟 | 读接口 p95 < 500 ms；连续 10 分钟超阈值告警 |
| 数据库 | 连接池等待、连接占用 > 80%、慢 SQL > 1 s 告警 |
| 业务一致性 | 资金/核销/合同/租控/库存幂等冲突异常增长告警 |
| 队列/外部服务 | 重试、死信、超时、降级次数和最老消息年龄告警 |
| 容量 | CPU/内存/磁盘 > 80%，连接数/请求量趋势告警 |

日志必须集中采集 `x-request-id`、操作者、租户/园区、业务动作和结果码；禁止记录密码、Token、完整手机号/证件号或正文附件。监控平台、通知渠道、值班表和告警演练因缺少外部环境仍是人工阻塞项。

## 5. 回滚与恢复

- 应用回滚：停止扩容和流量提升，切回上一不可变镜像 SHA；确认旧版本与当前 schema 兼容后恢复流量。
- 数据库回滚：只允许使用已在同一数据规模验证的 Alembic downgrade。若迁移产生不可逆数据转换，停止写入并由 DBA 从备份恢复到新实例，禁止原库上盲目回滚。
- 外部集成：关闭生产适配器或切换明确的降级路径；不得把 fake 成功当成恢复。
- 恢复后重复 `/health/ready`、关键 HTTP/浏览器旅程、数据对账与审计链检查，并记录 RTO/RPO 实测值。

## 6. 当前授权状态

`KWZY_PRODUCTION_DEPLOYMENT=AWAITING_HUMAN_APPROVAL`。模板存在不等于生产就绪；旧库快照、外部供应商凭据、移动端/小程序、大业务域和真实监控/灾备演练未关闭前不得部署。

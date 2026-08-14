# 设施设备、周巡检与 IoT 告警独立验收摘要

> 日期：2026-08-15（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`
> 证据性质：隔离工作树对精确提交 `e28678b5785b7f8bf03141bd7cffbd162932315b` 执行全量验收；机器报告 `acceptance-clean-e28678b.json`。
> 产品结论：本地 API + PC 设施运营纵切 `IMPLEMENTED_AND_VERIFIED`；真实 IoT 和真实旧库迁移未验收，全项目仍 `BLOCKED`。

## 已验证闭环

- 设备类型画像校验、租户/园区/单元范围、乐观更新、追加式前后快照历史和带依赖保护的受控退役。
- 巡检模板草稿/发布版本/退役、有序类型化检查项、精确设备周计划、暂停/恢复/退役及不可变任务快照。
- 独立 worker 的确定性周任务生成、重复安全漏检扫描、WorkItem/事件/审计投影和失败租户隔离。
- 指派开始/改派、类型化清单和安全证据提交、异常分级，以及关键异常对应一个稳定 WorkOrder。
- IoT 提供方 `NOT_CONNECTED/SANDBOX` 真相、无密钥凭据引用、租户/园区一致的版本化设备绑定与历史。
- 授权来源事件严格校验、同事件精确重放、同设备时间窗关联、严重度投影、确认/解决/关闭、重复安全升级和稳定 WorkOrder。
- PC 设施运营工作区的设备、周巡检和告警三视图；桌面抽屉下钻、角色只读/403/409、390px 离线/重试和无横向溢出。

## 精确提交总门禁

| 门禁 | 结果 |
| --- | --- |
| 全量脚本 | 35/35 步 exit 0，584,594 ms；HEAD `e28678b5785b7f8bf03141bd7cffbd162932315b` |
| PostgreSQL / Alembic | PostgreSQL 16；fresh base→`z2c80e5f6a64`；唯一 `current == heads`；down `z2→y1→z2`；1,495,479 bytes / 130 表备份删除恢复 |
| 后端 | 352 passed / 0 failed，174.94 s；错误级 Ruff 通过 |
| worker | Workbench 与 FacilityOps 各扫描 13 个租户，0 failed；设施已有任务 3 条且重复生成 0 |
| 前端 | ESLint 0 warning；vue-tsc 通过；3 文件/6 Vitest；144 modules production build |
| 浏览器 | 60 Playwright / 0 failed / 0 skipped；真实 PG16 + FastAPI + production Vite；设施主旅程 1/1 |
| OpenAPI | 14/14 契约测试及 YAML OpenAPI 3.1 strict；设施 runtime/YAML 32 个方法精确一致 |
| OpenSpec | 精确实现提交 strict 94/94；39 项任务和 8 份 delta |
| 性能 | 登录后 1000 请求、并发 25、预热 40；p95 320.076 ms、135.6 RPS、0% 错误 |
| 合成迁移 | 4 台设备、4 条历史、1 条隔离；dry/interruption/apply/reapply/reconcile/rollback 全部通过；伪造计划/绑定/告警均为 0 |
| 密钥扫描 | tracked + untracked non-ignored 982 文件，0 hits |

## 独立验收中发现并关闭

- `inspection:execute` 角色进入页面时被错误调用计划列表并要求 `inspection:read`：拆分读取能力，执行者不再因额外权限收到 403。
- 工单下钻新增真实链接后，旧宽泛文本断言产生多目标歧义：改为精确角色链接，证明点击的是关联 WorkOrder。
- 累积测试库存在同名计划导致证据选择不稳定：按唯一计划代码定位，不依赖展示名称。
- 告警 ACK 后异步刷新会清空用户已输入的必填解决原因：只在首次打开时初始化，确认→解决→关闭真实浏览器旅程通过。
- 重复执行产生同类告警时标题可能冲突：证据按唯一标题后缀定位，避免误取旧数据。

## 视觉证据

- `pc-desktop-inspection-exception-work-order.png`：桌面巡检失败详情、关键异常证据与关联工单下钻。
- `pc-desktop-iot-alarm-correlation.png`：桌面告警来源事件、关联计数、确认/解决输入与关联工单。
- `pc-mobile-facility-offline-retry.png`：390px 设备台账离线错误、重试和完整字段卡片，无横向溢出。

三张截图均来自全量 Playwright 的真实数据库/真实 HTTP/production build 运行，并已逐张人工复核。

## 不得外推的结论

- 提供方仅验证 `NOT_CONNECTED/SANDBOX`、签名/授权/幂等/降级契约；没有真实厂商凭据、协议和事件样本，不宣称 live IoT。
- 合成设施数据演练通过不等于真实迁移；缺授权旧 schema/字典、脱敏快照、主键映射和重复决策，真实迁移为 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`。
- 员工独立移动端、租户微信小程序、档案签章、HR、供应链、园企服务、驾驶舱和 AI 仍按总能力矩阵保持 `MISSING`。
- 未部署生产；生产部署和不可逆迁移继续等待人工授权。

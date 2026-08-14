# 租户服务与工单生命周期独立验收摘要

> 日期：2026-08-15（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`
> 证据性质：精确提交 `ffa72e2531396997cfe24ef1b1e42526cd4735fe` 全验收；机器报告 `acceptance-clean-ffa72e2.json`。
> 产品结论：本地 API + PC 租户服务/工单纵切 `IMPLEMENTED_AND_VERIFIED`；全项目仍 `BLOCKED`。

## 已验证闭环

- 数据库派生的 User→Party→园区租户服务授权，禁用后即时失效。
- 员工代受理和租户自助受理，来源幂等、联系方式脱敏、Party/园区/单元/联系人归属校验。
- 派单规则不可变版本、草稿/发布/显式退役、确定性匹配、自动派单、无匹配分诊待办和原因化人工改派。
- 响应/解决 SLA 截止时间快照、首次响应、重复安全的超时事件与状态投影。
- Decimal 服务端计价的版本报价、提交、Party 绑定接受/拒绝和报价前执行门禁。
- 追加式人工/材料/外包/其他成本、原因化冲正、报价与实际成本差异。
- 完工摘要与安全证据、返工保留历史、租户验收、一次性 1–5 评价、WorkItem/事件同步。
- PC 员工和租户角色工作区，桌面/390px 响应式、加载/空态/403/409/离线/重试和无横向溢出。

## 精确提交总门禁

| 门禁 | 结果 |
| --- | --- |
| 全量脚本 | 33/33 步 exit 0，554,324 ms；HEAD `ffa72e2531396997cfe24ef1b1e42526cd4735fe` |
| PostgreSQL / Alembic | PostgreSQL 16；fresh base→`y1b79d4e6f53`；唯一 `current == heads`；down -1→up；1,383,498 bytes / 114 表备份删除恢复 |
| 后端 | 342 passed / 0 failed，161.50 s；错误级 Ruff 通过 |
| 工单 PG 专项 | 2/2：复合租户/园区约束、评价唯一、并发派单、并发验收恰好一方成功 |
| 前端 | ESLint 0 warning；vue-tsc 通过；3 文件/6 Vitest；141 modules production build |
| 浏览器 | 59 Playwright / 0 failed / 0 skipped；真实 PG16 + FastAPI + production Vite；工单主旅程 1/1 |
| OpenAPI | 13/13 契约测试及 YAML OpenAPI 3.1 strict；工单 runtime/YAML 25 个方法精确一致 |
| OpenSpec | 精确实现提交 strict 86/86；39/39 任务；8 份主规格同步并归档后 strict 93/93 |
| 性能 | 登录后 1000 请求、并发 25、预热 40；p95 302.333 ms、132.87 RPS、0% 错误 |
| 合成迁移 | 3 工单、6 事件、1 隔离；dry/interruption/apply/reapply/reconcile/rollback 全部通过 |
| 密钥扫描 | tracked + untracked non-ignored 942 文件，0 hits |

## 整改中发现并关闭

- 跨 Party 复用受理幂等键可在主体校验前触达旧结果：改为先规范化并核对完整命令，跨主体和同键异载荷统一 409。
- 报价/验收同键重放未核对决定内容：只有完全相同命令可重放，改变决定或备注返回 409。
- 新增并发验收测试首次证明 `ACCEPTED` 与 `REWORK` 可因锁前预读双提交：改为先锁聚合再读幂等记录，PG16 证明一个成功、一个版本冲突。
- 伪造 JWT 中的 `work_order:dispatch` 不得扩大数据库角色权限；未知 body 字段 422、重复查询参数 400、跨 Party/租户/园区/联系人/子资源均 fail closed。
- Playwright 端口清理后存在残留服务竞争：启动前等待 8010/4173 真正释放，聚焦与全量浏览器均稳定通过。
- 旧主链仍调用已移除的“一步完成”：改为必填幂等键、合格处理人派单、版本化开工、完工摘要/证据和待租户验收。

## 视觉证据

- `pc-desktop-work-order-quote-waiting.png`：桌面员工工单详情、SLA、报价版本和不可变时间线。
- `pc-mobile-tenant-acceptance-rating.png`：390px 租户验收完成与评价，无横向溢出。
- `pc-mobile-tenant-offline-retry.png`：390px 离线受理失败保留表单并提供重试。

三张截图已人工逐张复核；移动抽屉使用视口截图，未再出现 `fullPage` 拼接造成的固定抽屉背景重叠伪影。

## 不得外推的结论

- 员工独立移动端、租户微信小程序、设备/周巡检/IoT、库存扣减、供应商结算不在本纵切，仍按能力矩阵保持 `MISSING`。
- SMS/企微、对象存储和其他供应商没有真实凭据，本地 fake/local/fail-closed 不等于 live。
- 合成 `repair_order` 演练通过不等于真实迁移；缺授权 schema/状态字典、脱敏快照、主键映射、附件清单和生产切换授权，真实迁移保持 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`。
- 未部署生产，生产部署仍等待人工授权。

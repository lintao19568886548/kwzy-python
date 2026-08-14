# 档案、电子签章与印章治理独立验收摘要

> 日期：2026-08-15（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`
> 证据性质：精确提交 `b04d738bc75e865e1c6bfb180e93dc9b95109cf3` 的全量验收；机器报告 `acceptance-clean-b04d738.json`。
> 产品结论：本地 API + PC 档案/签章/印章纵切 `IMPLEMENTED_AND_VERIFIED`；合法电子签厂商 live、真实旧库/二进制迁移未验收，全项目仍 `BLOCKED`。

## 已验证闭环

- 版本化档案分类与保管策略、确定性档号、精确附件版本归档、服务端 SHA-256、归档/完整性核验/不一致自动 hold 和追加式时间线。
- 法律保全的有因施加/解除，借阅申请、统一审批关联、借出/归还/过期，以及保管期限/依赖/审批门禁下的处置申请、双人确认和校验清单。
- 印章台账、园区范围、保管交接、丢失/停用/找回/退役及不可变保管历史。
- 精确档案版本的用印申请、统一审批、保管人执行；高风险申请人/最终审批人/执行人职责分离；含命令指纹的不可变幂等回执。
- 无密钥提供方注册、`NOT_CONNECTED/SANDBOX/CONNECTED/DEGRADED` 真相；精确版本信封、参与人、追加式提供方事件、授权重放安全沙箱投递，以及 live 配置 fail-closed。
- Lease 沙箱签章不再伪造法律 `SIGNED`，详情投影信封的真实状态。
- PC 档案与签章工作区覆盖桌面、平板和 390px；加载、空状态、403/409、离线/重试及真实提供方标签均通过。

## 精确提交总门禁

| 门禁 | 结果 |
| --- | --- |
| 全量脚本 | 36/36 步 exit 0，609,589 ms；HEAD `b04d738bc75e865e1c6bfb180e93dc9b95109cf3` |
| PostgreSQL / Alembic | PostgreSQL 16；fresh base→`b4ea2c7d8f86`；唯一 `current == heads`；down `b4→a3→b4`；1,595,978 bytes / 146 表备份删除恢复 |
| 后端 | 366 passed / 0 failed，188.68 s；错误级 Ruff 通过 |
| worker | Workbench 与 FacilityOps 多租户扫描通过，0 failed |
| 前端 | ESLint 0 warning；vue-tsc 通过；3 文件/6 Vitest；147 modules production build；仅有非阻塞 586.57 kB chunk 提示 |
| 浏览器 | 61 Playwright / 0 failed / 0 skipped；真实 PG16 + FastAPI + production Vite；全角色/响应式真栈通过 |
| OpenAPI | 15/15 契约测试及 YAML OpenAPI 3.1 strict；档案/印章/签章 runtime/YAML 33 个方法精确一致 |
| OpenSpec | 精确实现提交 strict 102/102；40/40 任务、11 份主规格同步并归档为 `2026-08-14-complete-records-signature-seal-governance`；归档后 strict 110/110 |
| 性能 | 登录后 1000 请求、并发 25、预热 40；p95 240.541 ms、146.259 RPS、0% 错误 |
| 合成迁移 | 2 分类、2 档案、2 版本、2 隔离；dry/interruption/apply/reapply/reconcile/rollback 全部通过；伪造印章、保管、提供方和事件均为 0 |
| 档案真实 HTTP | 21/21 阶段通过，926.41 ms；外部签章 `NOT_CONNECTED`；`production_contacted=false` |
| 密钥扫描 | tracked + untracked non-ignored 1,041 文件，0 hits |

## 独立验收中发现并关闭

- 高风险用印可由同一主体完成申请、最终审批和执行：增加职责分离硬门禁；仅允许具备 `seal:execute_override` 且填写审计原因的显式越权路径。
- 用印执行幂等键未绑定完整命令：增加请求指纹，完全重放返回原回执，变更请求体则返回冲突；前向迁移对既有行使用 fail-closed 哨兵值。
- 沙箱合同签署会写入法律 `SIGNED`：改为只投影信封真相，未连接的 live 提供方拒绝执行。
- 档案浏览器用例用全局“发送”定位器，在共享库多 DRAFT 信封时歧义：改为精确信封行内定位并通过全量回归。
- Party 企业画像在列表刷新前提前提示保存成功，紧接着提交关系会因共享 `saving` 状态静默返回：成功提示移到 `await load()` 后，Party 3 条与档案 1 条聚焦旅程及 61 条全量浏览器均通过。
- 视觉复核发现 390px 的第三个业务页签和档案表字段依赖横向滚动：页签改为三等分，档案/信封表改为带字段标签的完整卡片，并新增页签边界和表格容器无横向溢出断言。

## 视觉证据

- `pc-desktop-signature-truth.png`：桌面签章信封、参与人、提供方真相和事件时间线。
- `pc-tablet-signature-truth.png`：平板宽度的签章真相与可操作队列。
- `pc-mobile-records-offline-retry.png`：390px 档案离线错误、重试和完整卡片，无横向溢出。

三张截图均来自全量 Playwright 的真实数据库、真实 HTTP 和 production build，并已逐张人工复核。

## 不得外推的结论

- `SANDBOX` 只证明非法律测试闭环；真实电子签供应商、CA/时间戳/存证、生产印章设备没有协议、短期凭据和验厂证据，保持 `NOT_CONNECTED`。
- 合成元数据/二进制演练不等于真实迁移；缺授权旧 schema、脱敏样本、二进制、主键/分类/保管期限映射，真实迁移为 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_BINARIES_AND_KEYMAPS`。
- 员工独立移动端、租户微信小程序、HR、供应链、园企服务、驾驶舱、AI 和外部平台综合适配仍按总能力矩阵保持 `MISSING`。
- 未部署生产；生产部署、live 凭据和不可逆迁移继续等待人工授权。

# HR、排班、考勤、绩效与资质独立验收摘要

> 日期：2026-08-15（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`
> 产品结论：本地 API + PC 纵切达到 `IMPLEMENTED_AND_VERIFIED`；员工独立移动端、工资核算、真实设备和真实旧数据迁移不在此结论内，全项目仍为 `BLOCKED`。

## 已验证闭环

- 员工档案、明确的身份用户绑定、在职/停用/离职历史、乐观锁；手机号、证件号和证书号只保存掩码与独立密钥指纹。
- 不可变班次版本、员工日期排班、在职日期/已批请假/重复排班冲突和数据库并发唯一获胜。
- 可配置考勤策略、只保存加密配置引用的地点、幂等 IN/OUT 打卡、缺卡异常、工资准备态日汇总、有因人工调整和待办。
- 请假提交原生 Approval、审批状态刷新、取消和已批请假排班门禁；不以 HR 自有字段伪造审批完成。
- 绩效周期、员工目标权重、禁止自评、评价发布锁定和员工确认。
- 资质类型、同范围附件证据、证书号掩码/指纹、复核/吊销/到期扫描和幂等 WorkItem。
- 28 个 workforce 路径 runtime/YAML 方法精确一致；严格命令拒绝未知字段，重复查询参数、伪造 JWT 权限、跨租户/跨园区访问均 fail closed。
- PC 五个实时页签覆盖桌面、820px 平板和 390px 移动布局；真实数据库/HTTP/production build 验证加载、空态、权限、冲突、离线和重试。

## 当前专项门禁

| 门禁 | 结果 |
| --- | --- |
| PostgreSQL / Alembic | PG16 fresh base→`c5f02d8e9c87`；唯一 head；`c5→b4→c5`；`alembic check` 无漂移 |
| 后端专项 | 纯领域/API 6 passed；PG 模型/并发 2 passed；合成 ETL 5 passed；OpenAPI 全文件 16 passed；Ruff 通过 |
| 前端 | ESLint 0 warning；vue-tsc 通过；production Vite 150 modules；仅有非阻塞 chunk 大小提示 |
| 浏览器 | HR 真实栈 1/1 passed；PG16 + FastAPI + production Vite，桌面/平板/390px 与离线恢复 |
| 合成迁移 | 2 员工、1 班次版本、2 排班、3 打卡、2 汇总、1 请假、3 隔离；中断零残留、重跑零新增、对账/回滚通过 |
| 隐私真相 | 合成目标 PII 原文字段/精确坐标/轨迹列为 0；伪造绩效/资质/工资结果为 0 |
| 生产接触 | `production_contacted=false`，未获得生产部署或不可逆迁移授权 |

完整 clean-SHA 全量门禁、性能、备份恢复、主规格同步和归档将在实现提交后生成精确机器报告并更新本摘要；在此之前不得把专项结果外推为全项目验收通过。

## 视觉证据

- `pc-desktop-workforce-qualification.png`：桌面五页签、资质证据与外部设备/工资引擎真相。
- `pc-tablet-workforce-attendance.png`：平板考勤地点、打卡与 `MISSING_OUT` 异常汇总。
- `pc-mobile-workforce-offline-retry.png`：390px 当前导航可见、离线错误/重试、表格卡片和无页面级横向溢出。

截图来自真实 PG16、真实 FastAPI HTTP 和 production Vite 构建，并已逐张人工复核。

## 不得外推的结论

- `DEVICE/MOBILE` 仅证明受控接口和不持久化坐标；考勤机、生物识别、定位服务仍为 `NOT_CONNECTED`。
- 工资准备汇总不等于薪资、个税、社保或支付引擎；页面明确显示 `NOT_IMPLEMENTED`。
- PC 的 390px 响应式布局不等于员工独立移动端；能力矩阵第 11 项仍为 `MISSING`。
- 合成 ETL 不等于真实迁移。缺授权旧 schema、脱敏快照、主键/字典映射、审批证据和生产切换授权，真实迁移保持 `BLOCKED`。
- 未部署生产；生产部署继续等待人工授权。

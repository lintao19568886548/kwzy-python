# HR、排班、考勤、绩效与资质独立验收摘要

> 日期：2026-08-15（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`
> 精确 clean-SHA：`5577509a6ca2a473107038be1316a0ea9252fc8d`
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

## 精确 SHA 全量门禁

| 门禁 | 结果 |
| --- | --- |
| PostgreSQL / Alembic | PG16 fresh base→`c5f02d8e9c87`；唯一 head；`c5→b4→c5`；`alembic check` 无漂移 |
| 总控脚本 | 37/37 步 exit 0；07:34:32–07:45:28 +08:00；656,601 ms；0 failed |
| 后端 | 全量 380 passed（pytest 205.41 s）；Ruff 通过；worker 单周期无租户失败 |
| 前端 | ESLint 0 warning；vue-tsc 通过；production Vite 150 modules；仅有非阻塞 chunk 大小提示 |
| 浏览器 | 全量 62/62 passed（2.3 min）；HR 1/1 真实栈覆盖桌面/平板/390px 与离线恢复 |
| 真实 HTTP | HR 36/36 阶段、1,261.16 ms；请假原生审批、幂等/冲突、绩效、资质与跨租户隔离通过 |
| 性能 | 1000 请求/并发 25；p95 264.836 ms；145.596 RPS；0% 错误；门槛未降低 |
| 合成迁移 | 2 员工、1 班次版本、2 排班、3 打卡、2 汇总、1 请假、3 隔离；中断零残留、重跑零新增、对账/回滚通过 |
| 隐私真相 | 合成目标 PII 原文字段/精确坐标/轨迹列为 0；伪造绩效/资质/工资结果为 0 |
| 备份恢复 | `pg_dump -Fc` 1,697,402 bytes；删除/重建临时库后恢复并验证 162 张 public 表 |
| 契约/扫描 | OpenAPI 16/16 + YAML strict；精确 SHA 时 OpenSpec 111/111，9 份主规格同步归档后 119/119；1,091 文件 secrets scan 0 hits |
| 生产接触 | `production_contacted=false`，未获得生产部署或不可逆迁移授权 |

机器证据：`acceptance-clean-5577509.json`、`workforce-etl-clean-5577509.json`、`workforce-http-clean-5577509.json`、`http-performance-clean-5577509.json`。总报告 SHA-256 为 `EFC333223D2BB2C394E5F0F6882C51B8CF93F449F74570C41A6B322835E2C865`。

OpenSpec 36/36 任务完成，9 份 delta 主规格同步并归档为 `2026-08-14-complete-workforce-scheduling-attendance-performance`；归档后全量 strict 119/119。

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

# Party 企业画像纵切证据

> 生成日期：2026-08-14（Asia/Shanghai）
> 当前证据阶段：精确提交 `36805823ad2e88311b9744e9e720b282b7cc74c8` 的 clean-SHA 总验收通过。
> 产品边界：只声明本地产品范围完成；外部工商提供商、真实旧数据和生产切换均未获授权或证据。

## clean-SHA 机器证据

| 证据 | 结果 | SHA-256 |
| --- | --- | --- |
| `acceptance-clean-3680582.json` | 31/31 步骤 exit 0，521,943 ms | `FB03AA7BFC9F9D6024D657D3B39C7220536EAAFCDFAD994BE54199BA97BA963E` |
| `acceptance-clean-e7d7263-performance-failure.json` | 首轮在性能门禁以 p95 535.126 ms 真实中止，未降低 500 ms 门槛 | `905A449054C2547207DF2273DC64B81A89887FC9DE811559B1891223BA4B9908` |
| `http-performance-clean-3680582.json` | 1,000 请求，并发 25，p95 225.85 ms，172.617 RPS，0 错误 | `481E796A7CDCC0E260942C831CF9D2E2FC964EDFD9F24DB68FB55AFC4B73CE06` |
| `party-enterprise-etl-clean-3680582.json` | dry/interruption/apply/reapply/reconcile/rollback 全通过 | `13A8E8BDBAAF7F57445338BF8C42D9B8A971058F6B34043034EBC60CBA565C6E` |
| `party-enterprise-http-clean-3680582.json` | 21/21 真实 loopback HTTP 阶段通过，626.54 ms | `E14B6686A92B3D6F54D1AB89AFD043DE40E4A3BF0071FC76D9D603D80AE40C4F` |

首轮 clean-SHA 在企业目录 N+1 查询下触发真实性能失败。修复提交 `3680582` 将逐 Party 的园区和风险查询改为两个租户受限批量查询，并加入“查询数不随目录行数增长”的回归；随后从空库完整复跑才形成 PASS。

## 历史工作树证据

| 证据 | 结果 | SHA-256 |
| --- | --- | --- |
| `acceptance-worktree-20260814.json` | 31/31 步骤 exit 0，482,880 ms | `03266C7B0029F0576BFF7F40DF86472A81080DD4AD21EAFBEA95EAB7C2CE137D` |
| `http-performance-worktree.json` | 1,000 请求，并发 25，p95 409.791 ms，109.199 RPS，0 错误 | `A898900197E563E356684CE09DF1AD81153B03F8A2B85C5B9FE461487F96937E` |
| `party-enterprise-etl-worktree.json` | dry/interruption/apply/reapply/reconcile/rollback 全通过 | `B822AB7DAC5A93546A53D86EE3D7541BDC4705A8C64C02A475A259F3DB325210` |
| `party-enterprise-http-worktree.json` | 21/21 真实 loopback HTTP 阶段通过，671.22 ms | `931B3227FFBB3DE3BD72D3EDA881A28640C994497FCE2B55CB8F0E0ECB8DB5BF` |

clean-SHA 总脚本使用 PostgreSQL 16 空库执行 base→`t6c24e9f1a08`、唯一 current=head、t6→s5→t6；315 个后端测试、57 个 Playwright、11 个 OpenAPI 契约、71 项当时 OpenSpec、856 文件敏感信息扫描以及备份删除/恢复 100 张表均通过。

## 浏览器与视觉证据

- `pc-desktop-enterprise-conflict.png`：桌面管理员完成企业画像、关联企业、来源标签、风险处置和受控证件上传；并保留 409 冲突草稿。
- `pc-tablet-enterprise-readonly.png`：平板受限角色不读取受控证件 API，布局无横向溢出。
- `pc-mobile-enterprise-offline.png`：390×844 移动窄屏展示离线/重试和抽屉状态，无横向溢出。

三张截图已人工逐张检查：未发现假数据冒充、遮挡、重叠、乱码、不可读图表或可见敏感证件原文。外部工商状态明确显示 `NOT_CONNECTED`，界面没有伪造的“刷新成功”。

## 保持阻塞

- 未提供真实旧 schema、字段字典或经授权脱敏快照，迁移只能判 `CONDITIONAL_SYNTHETIC_ONLY`。
- 未提供外部工商数据提供商合同、沙箱凭据和回调协议，不能判 live verified。
- 未获得生产迁移、切换或部署授权。

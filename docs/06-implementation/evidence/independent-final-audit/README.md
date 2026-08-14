# 独立终验可视与性能证据（2026-08-14）

本目录由 repair 分支上的真实 PostgreSQL 16、FastAPI、生产 Vite 构建和浏览器会话生成。截图不是设计稿或静态 mock；登录、导航、数据抽屉和租控矩阵均来自真实 HTTP。浏览器控制台复核时 `error/warn` 为 0。

## 可视证据

| 文件 | 视口/场景 | SHA-256 |
|---|---|---|
| `03-contract-ledger-scroll-reset.jpg` | 1280px PC，跨路由后滚动位置已由 150 恢复为 0 | `9AC646957F983329D0DDBC0DAE29692A4F0BF27A88F192D9828C064ECB0CEA9F` |
| `04-contract-ledger-tablet.jpg` | 768×1024 合同台账，无页面横向溢出 | `5871017967C312BBBB0EFA999870C35A91774AF2B25385D69017254B3DB39EAA` |
| `05-contract-ledger-mobile.jpg` | 390×844 移动窄屏，无页面横向溢出 | `D726467CA1EBE59317CCB8CA03ACA0A4032FC0F90B39ECD92CADBC0D72D1E876` |
| `06-rent-control-tablet.jpg` | 768×1024 租控矩阵空状态 | `2988ECC9AE085DE0E1EDFE63ABDA76B1AF69F95E7D230B48C4864986E7B922F1` |
| `07b-rent-control-data-tablet-viewport.jpg` | 768×1024 租控矩阵真实种子数据 | `ECA9B09A84DCE65DFC57F9C6231DADC087776A7859F0971D68A2AE388A1369BE` |
| `08-contract-governance-drawer.jpg` | PC 合同治理抽屉与生命周期操作 | `4B25AA333E3967C311F4F2CA500E8EB88454320222598EF04E6B5D189D24E534` |

浏览器 full-page 截图会重复拼接固定头部，预修复的滚动截图也会裁掉页面标题，因此这些伪影文件未纳入证据目录。

## 精确提交机器验收

`acceptance-a9267d4.json` 绑定实现提交 `a9267d4c30096a7c80d66588ab06bc6838b32b0d`：2026-08-14 11:33:05–11:38:53（Asia/Shanghai），24/24 步 exit 0，总耗时 348,122 ms。报告 SHA-256：`E1D41D005DF3E8DB50C368FE58BC441A1D92AA658001EC2B3958CE58CFD2EF87`。

该机器报告覆盖 PG16 fresh/down-up、241 pytest、合成 ETL/回滚、真实 HTTP 性能、备份恢复、前端质量、40 Playwright、OpenAPI/OpenSpec、密钥扫描和清理。

## HTTP 性能证据

`http-performance.json`：loopback-only 真实登录后，轮询工作台、合同、客户和出租单元公共 API；1000 请求、并发 25、预热 40。

- 失败：0；错误率：0.0%。
- p50：145.961 ms；p95：280.422 ms；p99：321.082 ms；最大：333.336 ms。
- 吞吐：141.36 req/s。
- 门槛：p95 ≤ 500 ms、错误率 ≤ 1%、吞吐 ≥ 20 req/s；本地实现切片结果 `PASS`。
- 报告 SHA-256：`A13D9450E5D11C084FAA1E1A586687EA8BF96F828E4C08947322A98FFAAA883B`。

该性能结果是本机实现切片基线，不代表生产容量或全部缺失业务域的性能验收。

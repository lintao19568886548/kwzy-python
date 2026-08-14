# 外部集成接入 Runbook

`LIVE_EXTERNAL_INTEGRATION=NOT_VERIFIED` 时仍可完成代码重构。

## 招商渠道接收

| 项 | 说明 |
| --- | --- |
| 渠道配置 | 默认禁用；保存不可枚举 public id、默认园区、字段映射和 `secret_env_key`，不保存明文 secret |
| 密钥 | 由部署环境按渠道配置引用注入；缺失时 fail closed |
| 签名 | `v1\n<unix_timestamp>\n<external_event_id>\n<sha256(raw_body)>` 的 HMAC-SHA256；固定时间比较 |
| 重放保护 | 时间窗 + `(channel_id, external_event_id)` 唯一；同事件返回同一 inbox/Lead |
| 隔离 | 映射失败保存摘要、稳定原因和脱敏预览，不记录原始 secret/完整 PII |
| 状态 | 本地 fixture 只能标 `LOCAL_CONTRACT_VERIFIED`；真实沙箱证据到位后才能标 `SANDBOX_VERIFIED`，生产仍需另行审批 |

禁止渠道载荷指定内部 owner、permission、approval status、lock 或 contract。真实厂商协议、IP 白名单、证书、签名差异、限流和沙箱凭据未取得时保持 `NOT_CONNECTED/BLOCKED_EXTERNAL`。

## 短信 SMS

| 变量 | 说明 |
| --- | --- |
| `SMS_PROVIDER` | `auto` / `fake` / `production` |
| `SMS_API_KEY` | 生产必填（provider=production） |
| `SMS_ENDPOINT` | 供应商地址 |
| `SMS_TIMEOUT_SECONDS` | 默认 5 |
| `SMS_MAX_RETRIES` | 默认 2 |

本地/test：`auto` → Fake。生产 `production` 且无 key 启动失败。

## 微信

| 变量 | 说明 |
| --- | --- |
| `WECHAT_PROVIDER` | `auto` / `production` |
| `WECHAT_APP_ID` | |
| `WECHAT_APP_SECRET` | |

## 对象存储

| 变量 | 说明 |
| --- | --- |
| `OSS_PROVIDER` | `auto` / `local` / `s3` |
| `OSS_LOCAL_ROOT` | 本地目录 |
| `OSS_ENDPOINT` / `OSS_BUCKET` / `OSS_ACCESS_KEY` / `OSS_SECRET_KEY` | S3 |

失败记录：`integration_outbox` 表 + `/integrations/outbox`。

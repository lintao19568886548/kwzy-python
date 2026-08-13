# 外部集成接入 Runbook

`LIVE_EXTERNAL_INTEGRATION=NOT_VERIFIED` 时仍可完成代码重构。

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

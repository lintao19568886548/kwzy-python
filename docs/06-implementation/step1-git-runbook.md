# Step1 本地 Git 保护 Runbook

> 关联：`close-step1-acceptance-gaps` 任务 7  
> **默认不由代理自动执行 `git init` / commit / push**

## 1. 忽略清单（已写入仓库根 `.gitignore`）

- `.env`、密钥文件  
- `*.db`、`*.backup.*`、SQLite 旁路文件  
- `.venv/`、`__pycache__/`、测试/缓存  
- IDE 目录  

## 2. 建议初始化（人工执行）

```bash
cd D:\重构python\kwzy-python
git init
git add .
git status   # 确认无 .db / .env
git commit -m "chore(step1): baseline Identity+Park+Unit after acceptance-gaps closed"
```

## 3. 禁止事项

- 不配置 remote、不推送 GitHub（除非产品明确要求）  
- 不将 SQLite 与备份纳入版本库  
- 不提交真实 `LOCAL_ADMIN_PASSWORD`  

## 4. 迁移失败回滚（文件级优先）

1. 停止 API 进程  
2. 用同目录备份覆盖：`kwzy_step1.backup.YYYYMMDD-HHMMSS.db` → `kwzy_step1.db`  
3. 仅在代码已回退且确认安全时再考虑 `alembic downgrade`  

# KWZY ETL / 迁移工具（骨架）

## 边界

- **禁止**连接真实生产旧库
- 使用脱敏 fixture、结构快照或安全副本
- 支持 dry-run / 批处理 / 幂等设计目标

## 结构

```text
tools/etl/
  mapping/table_map.v1.yaml   # 旧表→新表
  dry_run.py                  # 只读校验映射完整性
  fixtures/                   # 脱敏样例（可选）
```

## 用法

```bash
python tools/etl/dry_run.py
python tools/etl/dry_run.py --mapping tools/etl/mapping/table_map.v1.yaml
python tools/etl/run_asset_etl_drill.py --database-url postgresql+psycopg://... --out infra/local-staging/out/asset_etl/asset_etl.json
```

退出码：映射缺字段或非法状态时非 0。

## 状态

`KWZY_DATA_MIGRATION_READINESS=CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA` —
核心与资产合成数据已具备校验、首次应用、幂等重跑、对账与隔离回滚演练；
真实旧库仍需结构快照、脱敏样例和人工映射裁决，生产切换未获授权。

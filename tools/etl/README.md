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
```

退出码：映射缺字段或非法状态时非 0。

## 状态

`KWZY_DATA_MIGRATION_READINESS=NOT_READY` — 仅骨架与核心表映射草案，未做全量字段闭合与演练。

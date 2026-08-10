# Phase06 Lease Contract 实施完成报告

> 分支：`feat/lease-contract`  
> OpenSpec：`implement-lease-contract`  
> Parent：`feat/party-master`  

## 范围

已实现：

- 合同 DRAFT / PENDING_ACTIVE / ACTIVE / TERMINATED / BREACHED / CANCELLED 生命周期  
- 占用单元行、条款行  
- activate 冲突检测与 `units.used_area` 投影  
- tenant 隔离、park scope、权限 `lease:*`  
- Alembic `d4b02c3f5a21`  

未实现（按设计延期）：

- Bill / Payment / 出账  
- 押金退还流水  
- 旧 rental 适配  
- EXPIRING 定时任务  

## 验证

- SQLite/PG base→head；PG down/up  
- 全量 pytest 74 passed  
- openspec strict valid  
- 容器已停止  

## 标记

`PHASE06-LEASE-CONTRACT-IMPLEMENTATION-COMPLETE`

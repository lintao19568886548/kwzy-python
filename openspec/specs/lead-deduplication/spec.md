# lead-deduplication Specification

## Purpose
定义基于规范化电话、企业名称和来源外部键的线索重复候选、授权覆盖与合并治理。该规格确保高置信重复默认被阻止、隐私字段按范围脱敏，并在合并后保留完整血缘而不重复计算漏斗。

## Requirements

### Requirement: Deterministic duplicate candidates
系统 MUST 使用租户内规范化电话、规范化企业名称和来源外部键返回带原因的重复候选，并仅返回用户有权查看的最小必要字段。

#### Scenario: Exact phone candidate
- **WHEN** 新线索的规范化电话与现有未合并线索相同
- **THEN** 创建预检返回候选 ID、匹配原因和当前阶段，不静默创建第二主档

#### Scenario: Public pool privacy
- **WHEN** 普通销售查询尚未领取的公海重复候选
- **THEN** 电话和联系人敏感字段被脱敏，完整数据不泄露

### Requirement: Controlled duplicate override
系统 MUST 默认以 409 阻止高置信重复创建，只有具备写权限且提交非空覆盖理由时才允许创建并记录审计。

#### Scenario: Missing override reason
- **WHEN** 存在高置信重复且请求未提交覆盖理由
- **THEN** 返回 `LEAD_DUPLICATE` 409 和候选摘要，数据库无新增线索

### Requirement: Merge preserves lineage
具备 `lead:manage` 的用户 MUST 能在同租户同园区内合并两个非终态冲突线索，来源线索标记 `MERGED` 并保留活动、分配和 merge 血缘。

#### Scenario: Successful merge
- **WHEN** 管理员以当前版本将重复来源合并到保留线索
- **THEN** 来源不可再写、指向保留线索，详情仍可查询两边历史且不得重复计算漏斗

#### Scenario: Cross-scope merge denied
- **WHEN** 两条线索不属于同一租户/园区或任一已转化
- **THEN** 合并失败且所有记录保持原状

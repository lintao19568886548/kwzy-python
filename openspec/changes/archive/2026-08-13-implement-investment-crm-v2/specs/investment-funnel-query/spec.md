## ADDED Requirements

### Requirement: Shared scoped funnel filters
列表、看板和漏斗 MUST 使用同一 tenant/park/owner/pool/stage/source/keyword/time 过滤器及所有权可见规则。

#### Scenario: Filter reconciliation
- **WHEN** 用户以相同园区、来源和时间范围查询列表与漏斗
- **THEN** 各阶段计数之和等于同过滤条件下未合并线索总数

### Requirement: Operational funnel metrics
系统 MUST 返回新增、开放、转化、丢失、公海、逾期跟进、阶段分布、转化率和平均首跟进时长，并明确使用当前状态和 UTC 时间口径。

#### Scenario: Zero denominator
- **WHEN** 过滤范围内没有线索
- **THEN** 所有 count 为 0、比例为 0、平均时长为 null 或约定零值且无除零错误

#### Scenario: Merged source excluded
- **WHEN** 来源线索已合并到保留线索
- **THEN** 来源历史可查但不重复计入当前漏斗、新增或转化分母

### Requirement: Stable grouped breakdown
系统 MUST 按来源和负责人返回稳定排序的分组指标，且不得泄露用户无权读取的负责人私有线索。

#### Scenario: Ordinary seller breakdown
- **WHEN** 普通销售查询负责人分组
- **THEN** 只返回本人和公海允许的聚合，不暴露其他销售名称或数量

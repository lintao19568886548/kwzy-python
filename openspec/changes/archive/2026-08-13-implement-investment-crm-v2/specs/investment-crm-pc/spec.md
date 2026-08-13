## ADDED Requirements

### Requirement: CRM workspace navigation and filters
PC MUST 提供授权园区选择、指标卡、阶段看板/列表、公海、来源/负责人/阶段/时间/关键词过滤，且不得要求用户手填园区、负责人或线索内部 ID。

#### Scenario: Primary desktop workflow
- **WHEN** 招商管理员进入 `/leads` 并选择园区
- **THEN** 可查看一致漏斗，在看板/列表间切换，打开线索详情并完成创建、分配、跟进、匹配、锁房和转化允许动作

### Requirement: Lead detail timeline and actions
详情 MUST 展示基础资料、阶段、负责人/公海、重复候选、活动时间线、分配历史、房源匹配/锁、下一跟进及 Party/Lease 转化结果。

#### Scenario: Conflict feedback
- **WHEN** 领取、更新或锁房返回 409
- **THEN** 页面保留用户上下文、显示可操作冲突原因并刷新受影响的最新版本，而不是静默覆盖

### Requirement: Permission-consistent states
PC MUST 根据权限和所有权隐藏或禁用写操作，并实现 loading、empty、error、forbidden、success 和 read-only 状态；服务器授权仍为最终边界。

#### Scenario: Read-only seller
- **WHEN** 用户仅有 `lead:read`
- **THEN** 可浏览允许的本人/公海信息，但创建、分配、跟进、锁房、合并和转化控件不可用，直接 API 写请求仍返回 403

### Requirement: Responsive and accessible interaction
工作台 MUST 在桌面和平板宽度无页面级横向溢出，并为园区、过滤、看板、列表、抽屉和主要动作提供语义标签、可见焦点与键盘路径。

#### Scenario: Tablet keyboard flow
- **WHEN** 键盘用户在平板宽度操作工作台
- **THEN** 可依次到达园区、过滤、视图切换、线索卡/行、详情和许可的主要动作

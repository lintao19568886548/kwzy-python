# 预发布验收材料清单（模板，状态 NOT_RUN）

> 本文件可随预发布执行勾选；**当前未执行远程预发布**。

## 环境身份

- [ ] 预发布 URL / 集群名称书面确认  
- [ ] 非生产数据库（PG16）连接串（密钥不入库）  
- [ ] 镜像 tag = main HEAD  

## 数据库

- [ ] `alembic upgrade head` 成功  
- [ ] `alembic downgrade -1` + `upgrade head` 往返  
- [ ] 种子账号仅用临时密码  

## 功能冒烟

- [ ] 登录 / refresh / logout  
- [ ] 工作台 summary  
- [ ] Party → Lease → Bill → Payment  
- [ ] Lead convert  
- [ ] Work order complete  
- [ ] Collection case create  
- [ ] System org/dict/params  

## 安全

- [ ] 生产 env 未启用匿名  
- [ ] 无默认弱 JWT  
- [ ] 密钥扫描通过  

## 结论栏

| 项 | 值 |
| --- | --- |
| `KWZY_STAGING_ACCEPTANCE` | `NOT_RUN` |
| 执行人 | — |
| 日期 | — |

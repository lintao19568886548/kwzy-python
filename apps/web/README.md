# KWZY Web（创新前端）

Vue 3 + TypeScript + Vite + Pinia + Vue Router。

## 设计原则

- 工作台优先：待办、逾期、未结、到期合同
- 主链钻取：主体 → 合同 → 账单 → 收款
- 不照抄旧 vben 页面布局
- 权限与 token 经统一请求层

## 开发

```bash
cd apps/web
npm install
npm run dev
```

代理：`/api` → `http://127.0.0.1:8000`

## 状态

脚手架 + 登录/工作台/主链列表。**非**全前端替代完成。

# ADR: 目标前端技术栈

## 状态

Accepted（2026-08-13）

## 背景

旧前端为 Java monorepo 内 `playground`（Vue + 大量 vben 体系页面）。新系统需创新式重构，不机械照搬。

## 决策

采用：

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- axios 统一请求层
- 轻量自研布局（首期不引入完整组件库，避免绑定旧皮肤）

目录：`apps/web`

## 后果

- 与后端 `/api/v1` envelope 对齐
- 后续可换 Element Plus / Naive UI 而不改领域 API
- E2E 与权限指令在后续 change 补齐

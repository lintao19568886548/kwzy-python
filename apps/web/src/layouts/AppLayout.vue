<script setup lang="ts">
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

function logout() {
  auth.logout();
  router.push({ name: "login" });
}
</script>

<template>
  <div class="shell">
    <aside class="side card">
      <div class="brand">KWZY 园区</div>
      <nav>
        <router-link to="/workbench">工作台</router-link>
        <router-link to="/todos">待办</router-link>
        <router-link to="/leads">招商</router-link>
        <router-link to="/work-orders">工单</router-link>
        <router-link to="/parties">主体</router-link>
        <router-link to="/leases">合同</router-link>
        <router-link to="/bills">账单</router-link>
        <router-link to="/payments">收款</router-link>
        <router-link to="/system">系统</router-link>
      </nav>
      <div class="side-foot">
        <div class="muted">{{ auth.username || "已登录" }}</div>
        <button class="btn-ghost btn" type="button" @click="logout">退出</button>
      </div>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
  gap: 1rem;
  padding: 1rem;
}
.side {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.brand {
  font-weight: 700;
  font-size: 1.15rem;
  color: var(--primary);
}
nav {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
nav a {
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  color: var(--muted);
}
nav a.router-link-active {
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 600;
}
.side-foot {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.main {
  min-width: 0;
}
@media (max-width: 900px) {
  .shell {
    grid-template-columns: 1fr;
  }
}
</style>

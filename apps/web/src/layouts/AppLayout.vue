<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const mainNav = ref<HTMLElement | null>(null);

type NavItem = {
  to: string;
  label: string;
  testid: string;
  permission?: string | string[];
  permissionAny?: string[];
};

const allNav: NavItem[] = [
  { to: "/workbench", label: "工作台", testid: "nav-workbench", permission: "work_item:read" },
  { to: "/todos", label: "待办", testid: "nav-todos", permission: "work_item:read" },
  { to: "/leads", label: "招商", testid: "nav-leads", permission: "lead:read" },
  {
    to: "/work-orders",
    label: "租户服务",
    testid: "nav-work-orders",
    permissionAny: ["work_order:read", "tenant_service:read_own"],
  },
  { to: "/parks", label: "园区", testid: "nav-parks", permission: "park:read" },
  { to: "/rent-control", label: "资产租控", testid: "nav-rent-control", permission: "unit:read" },
  { to: "/parties", label: "主体", testid: "nav-parties", permission: "party:read" },
  { to: "/leases", label: "合同", testid: "nav-leases", permission: "lease:read" },
  { to: "/bills", label: "账单", testid: "nav-bills", permission: "bill:read" },
  { to: "/receipts", label: "到账中心", testid: "nav-receipts", permission: "payment:read" },
  { to: "/payments", label: "收款", testid: "nav-payments", permission: "payment:read" },
  { to: "/collection", label: "催缴", testid: "nav-collection", permission: "collection:read" },
  {
    to: "/approvals",
    label: "审批审计",
    testid: "nav-approvals",
    permissionAny: [
      "approval:read",
      "approval:write",
      "approval.task.read",
      "approval.task.decide",
      "approval.definition.read",
      "approval.definition.write",
      "approval.delegation.manage",
      "audit.read",
    ],
  },
  {
    to: "/system",
    label: "系统",
    testid: "nav-system",
    permission: ["identity.user.read", "identity.org.read"],
  },
];

const navItems = computed(() =>
  allNav.filter((item) => {
    if (auth.can("*")) return true;
    if (item.permissionAny) {
      return item.permissionAny.some((permission) => auth.can(permission));
    }
    if (!item.permission) return true;
    return auth.can(item.permission);
  })
);

const denied = computed(() => route.query.denied === "1");

async function revealActiveNavItem() {
  await nextTick();
  if (!window.matchMedia("(max-width: 900px)").matches) return;
  const activeLink = mainNav.value?.querySelector<HTMLElement>("a.router-link-active");
  activeLink?.scrollIntoView({ behavior: "auto", block: "nearest", inline: "center" });
}

onMounted(revealActiveNavItem);
watch(() => route.fullPath, revealActiveNavItem);

async function logout() {
  await auth.logout();
  await router.push({ name: "login" });
}
</script>

<template>
  <div class="shell" data-testid="app-shell">
    <aside class="side card">
      <div class="brand">KWZY 园区</div>
      <nav ref="mainNav" data-testid="main-nav">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          :data-testid="item.testid"
        >
          {{ item.label }}
        </router-link>
      </nav>
      <div class="side-foot">
        <div class="muted" data-testid="auth-username">{{ auth.username || "已登录" }}</div>
        <button class="btn-ghost btn" type="button" data-testid="logout-btn" @click="logout">
          退出
        </button>
      </div>
    </aside>
    <main class="main">
      <p v-if="denied" class="error" data-testid="denied-banner">无权限访问目标页面，已重定向</p>
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
    grid-template-rows: auto minmax(0, 1fr);
    align-content: start;
  }
  .side {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem;
  }
  nav {
    flex-direction: row;
    gap: 0.25rem;
    overflow-x: auto;
    scroll-padding-inline: 0.75rem;
    scroll-snap-type: x proximity;
    scrollbar-width: thin;
  }
  nav a {
    flex: 0 0 auto;
    padding: 0.45rem 0.65rem;
    scroll-snap-align: center;
    white-space: nowrap;
  }
  .side-foot {
    margin-top: 0;
    flex-direction: row;
    align-items: center;
  }
  .side-foot .muted {
    display: none;
  }
  .side-foot .btn {
    padding: 0.45rem 0.7rem;
  }
}
@media (max-width: 560px) {
  .side {
    grid-template-columns: 1fr auto;
  }
  nav {
    grid-column: 1 / -1;
    grid-row: 2;
  }
}
</style>

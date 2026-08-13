import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import LoginView from "@/views/LoginView.vue";
import AppLayout from "@/layouts/AppLayout.vue";
import WorkbenchView from "@/views/WorkbenchView.vue";
import PartiesView from "@/views/PartiesView.vue";
import LeasesView from "@/views/LeasesView.vue";
import BillsView from "@/views/BillsView.vue";
import PaymentsView from "@/views/PaymentsView.vue";
import TodosView from "@/views/TodosView.vue";
import LeadsView from "@/views/LeadsView.vue";
import WorkOrdersView from "@/views/WorkOrdersView.vue";
import SystemAdminView from "@/views/SystemAdminView.vue";
import CollectionCasesView from "@/views/CollectionCasesView.vue";
import ApprovalsView from "@/views/ApprovalsView.vue";
import ParksView from "@/views/ParksView.vue";
import ForbiddenView from "@/views/ForbiddenView.vue";

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "login", component: LoginView, meta: { public: true } },
  {
    path: "/",
    component: AppLayout,
    children: [
      { path: "", redirect: "/workbench" },
      {
        path: "forbidden",
        name: "forbidden",
        component: ForbiddenView,
      },
      {
        path: "workbench",
        name: "workbench",
        component: WorkbenchView,
        meta: { permission: "work_item:read" },
      },
      {
        path: "todos",
        name: "todos",
        component: TodosView,
        meta: { permission: "work_item:read" },
      },
      { path: "leads", name: "leads", component: LeadsView, meta: { permission: "lead:read" } },
      {
        path: "work-orders",
        name: "work-orders",
        component: WorkOrdersView,
        meta: { permission: "work_order:read" },
      },
      {
        path: "collection",
        name: "collection",
        component: CollectionCasesView,
        meta: { permission: "collection:read" },
      },
      {
        path: "approvals",
        name: "approvals",
        component: ApprovalsView,
        meta: { permission: "approval:read" },
      },
      {
        path: "parks",
        name: "parks",
        component: ParksView,
        meta: { permission: "park:read" },
      },
      {
        path: "parties",
        name: "parties",
        component: PartiesView,
        meta: { permission: "party:read" },
      },
      {
        path: "leases",
        name: "leases",
        component: LeasesView,
        meta: { permission: "lease:read" },
      },
      { path: "bills", name: "bills", component: BillsView, meta: { permission: "bill:read" } },
      {
        path: "payments",
        name: "payments",
        component: PaymentsView,
        meta: { permission: "payment:read" },
      },
      {
        path: "system",
        name: "system",
        component: SystemAdminView,
        meta: { permission: ["identity.user.read", "identity.org.read"] },
      },
    ],
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  // Ensure permissions loaded when only token is present (hard navigation / refresh)
  if (auth.accessToken && auth.permissions.length === 0 && !auth.username) {
    try {
      await auth.fetchMe();
    } catch {
      auth.clearSession();
    }
  }
  if (!to.meta.public && !auth.isAuthed) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.isAuthed) {
    if (auth.can("work_item:read") || auth.can("*")) return { name: "workbench" };
    if (auth.can("party:read")) return { name: "parties" };
    return { name: "forbidden" };
  }
  const perm = to.meta.permission as string | string[] | undefined;
  if (perm && auth.isAuthed && !auth.can(perm) && !auth.can("*")) {
    return { name: "forbidden", query: { denied: "1", from: String(to.fullPath) } };
  }
  return true;
});

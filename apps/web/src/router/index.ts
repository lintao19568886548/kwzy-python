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

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "login", component: LoginView, meta: { public: true } },
  {
    path: "/",
    component: AppLayout,
    children: [
      { path: "", redirect: "/workbench" },
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

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isAuthed) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.isAuthed) {
    return { name: "workbench" };
  }
  const perm = to.meta.permission as string | string[] | undefined;
  if (perm && auth.isAuthed && !auth.can(perm) && !auth.can("*")) {
    return { name: "workbench", query: { denied: "1" } };
  }
  return true;
});

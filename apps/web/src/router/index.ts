import { createRouter, createWebHistory } from "vue-router";
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

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    {
      path: "/",
      component: AppLayout,
      children: [
        { path: "", redirect: "/workbench" },
        { path: "workbench", name: "workbench", component: WorkbenchView },
        { path: "todos", name: "todos", component: TodosView },
        { path: "leads", name: "leads", component: LeadsView },
        { path: "work-orders", name: "work-orders", component: WorkOrdersView },
        { path: "parties", name: "parties", component: PartiesView },
        { path: "leases", name: "leases", component: LeasesView },
        { path: "bills", name: "bills", component: BillsView },
        { path: "payments", name: "payments", component: PaymentsView },
        { path: "system", name: "system", component: SystemAdminView },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isAuthed) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.isAuthed) {
    return { name: "workbench" };
  }
  return true;
});

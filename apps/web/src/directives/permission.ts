import type { App, Directive } from "vue";
import { useAuthStore } from "@/stores/auth";

function allowed(value: string | string[] | undefined): boolean {
  if (!value) return true;
  const auth = useAuthStore();
  const need = Array.isArray(value) ? value : [value];
  if (auth.permissions.includes("*")) return true;
  return need.every((code) => auth.permissions.includes(code));
}

export const vPermission: Directive<HTMLElement, string | string[]> = {
  mounted(el, binding) {
    if (!allowed(binding.value)) {
      el.style.display = "none";
      el.setAttribute("aria-hidden", "true");
      el.dataset.permissionDenied = "1";
    }
  },
  updated(el, binding) {
    if (!allowed(binding.value)) {
      el.style.display = "none";
      el.dataset.permissionDenied = "1";
    } else {
      el.style.display = "";
      delete el.dataset.permissionDenied;
    }
  },
};

export function registerPermission(app: App) {
  app.directive("permission", vPermission);
}

export function hasPermission(code: string | string[]): boolean {
  return allowed(code);
}

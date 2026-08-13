import { defineStore } from "pinia";
import { http } from "@/api/http";
import type { Envelope } from "@/api/types";

type LoginData = {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  user?: { id?: number; username?: string; real_name?: string };
};

const TOKEN_KEY = "kwzy_access_token";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    accessToken: localStorage.getItem(TOKEN_KEY) || "",
    username: "" as string,
    realName: "" as string,
    permissions: [] as string[],
    parkIds: [] as number[],
    userId: 0 as number,
    tenantId: 0 as number,
  }),
  getters: {
    isAuthed: (s) => Boolean(s.accessToken),
  },
  actions: {
    _persist() {
      if (this.accessToken) localStorage.setItem(TOKEN_KEY, this.accessToken);
      else localStorage.removeItem(TOKEN_KEY);
    },
    async login(username: string, password: string, tenantCode?: string) {
      const body: Record<string, string> = { username, password };
      if (tenantCode) body.tenant_code = tenantCode;
      const { data } = await http.post<Envelope<LoginData>>("/auth/login", body);
      this.accessToken = data.data.access_token;
      this.username = data.data.user?.username || username;
      this._persist();
      await this.fetchMe();
    },
    async refresh() {
      const { data } = await http.post<Envelope<LoginData>>("/auth/refresh", {});
      this.accessToken = data.data.access_token;
      this._persist();
      await this.fetchMe();
    },
    async fetchMe() {
      const { data } = await http.get<Envelope<Record<string, unknown>>>("/auth/me");
      this.username = String(data.data.username || this.username);
      this.realName = String(data.data.real_name || "");
      this.userId = Number(data.data.id || data.data.user_id || 0);
      this.tenantId = Number(data.data.tenant_id || 0);
      const perms = data.data.permissions;
      this.permissions = Array.isArray(perms) ? (perms as string[]) : [];
      const parks = data.data.park_ids;
      this.parkIds = Array.isArray(parks) ? parks.map((x) => Number(x)) : [];
    },
    async logout() {
      try {
        await http.post("/auth/logout", {});
      } catch {
        // ignore logout network errors
      }
      this.clearSession();
    },
    clearSession() {
      this.accessToken = "";
      this.username = "";
      this.realName = "";
      this.permissions = [];
      this.parkIds = [];
      this.userId = 0;
      this.tenantId = 0;
      this._persist();
    },
    can(code: string | string[]): boolean {
      if (this.permissions.includes("*")) return true;
      const need = Array.isArray(code) ? code : [code];
      return need.every((c) => this.permissions.includes(c));
    },
  },
});

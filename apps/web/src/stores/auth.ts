import { defineStore } from "pinia";
import { http } from "@/api/http";
import type { Envelope } from "@/api/types";

type LoginData = {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  user?: { id?: number; username?: string; real_name?: string };
};

const TOKEN_KEY = "kwzy_access_token";
const REFRESH_KEY = "kwzy_refresh_token";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    accessToken: localStorage.getItem(TOKEN_KEY) || "",
    refreshToken: localStorage.getItem(REFRESH_KEY) || "",
    username: "" as string,
    permissions: [] as string[],
  }),
  getters: {
    isAuthed: (s) => Boolean(s.accessToken),
  },
  actions: {
    async login(username: string, password: string) {
      const { data } = await http.post<Envelope<LoginData>>("/auth/login", {
        username,
        password,
      });
      this.accessToken = data.data.access_token;
      this.refreshToken = data.data.refresh_token || "";
      this.username = data.data.user?.username || username;
      localStorage.setItem(TOKEN_KEY, this.accessToken);
      if (this.refreshToken) {
        localStorage.setItem(REFRESH_KEY, this.refreshToken);
      }
      await this.fetchMe();
    },
    async fetchMe() {
      try {
        const { data } = await http.get<Envelope<Record<string, unknown>>>("/auth/me");
        this.username = String(data.data.username || this.username);
        const perms = data.data.permissions;
        this.permissions = Array.isArray(perms) ? (perms as string[]) : [];
      } catch {
        // me 失败时保留 token，页面可再试
      }
    },
    logout() {
      this.accessToken = "";
      this.refreshToken = "";
      this.username = "";
      this.permissions = [];
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
    },
  },
});

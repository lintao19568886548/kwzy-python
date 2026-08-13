import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth";

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api/v1",
  timeout: 20000,
});

let refreshing: Promise<void> | null = null;

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const auth = useAuthStore();
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`;
  }
  return config;
});

http.interceptors.response.use(
  (resp) => {
    const body = resp.data;
    if (body && typeof body === "object" && "code" in body && body.code !== "OK") {
      return Promise.reject(new Error(body.message || body.code || "请求失败"));
    }
    return resp;
  },
  async (err: AxiosError<{ message?: string; code?: string }>) => {
    const status = err.response?.status;
    const original = err.config as InternalAxiosRequestConfig & { _retry?: boolean };
    const auth = useAuthStore();

    if (status === 401 && original && !original._retry && auth.refreshToken) {
      original._retry = true;
      try {
        if (!refreshing) {
          refreshing = auth.refresh().finally(() => {
            refreshing = null;
          });
        }
        await refreshing;
        original.headers = original.headers || {};
        original.headers.Authorization = `Bearer ${auth.accessToken}`;
        return http.request(original);
      } catch {
        auth.clearSession();
      }
    }

    if (status === 401 || status === 403) {
      // permission expired — leave session clear on 401 after refresh fail
    }

    const msg =
      err.response?.data?.message ||
      err.response?.data?.code ||
      err.message ||
      "网络错误";
    return Promise.reject(new Error(msg));
  }
);

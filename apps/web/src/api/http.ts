import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth";

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
    public readonly data: unknown = null
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api/v1",
  timeout: 20000,
  withCredentials: true,
  headers: { "X-Client-Platform": "pc" },
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
      return Promise.reject(
        new ApiRequestError(body.message || body.code || "请求失败", body.code, resp.status, body.data)
      );
    }
    return resp;
  },
  async (err: AxiosError<{ message?: string; code?: string; data?: unknown }>) => {
    const status = err.response?.status;
    const original = err.config as InternalAxiosRequestConfig & { _retry?: boolean };
    const auth = useAuthStore();

    const isAuthEndpoint = String(original?.url || "").includes("/auth/");
    if (status === 401 && original && !original._retry && !isAuthEndpoint) {
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
    return Promise.reject(
      new ApiRequestError(
        msg,
        err.response?.data?.code || "NETWORK_ERROR",
        status || 0,
        err.response?.data?.data ?? null
      )
    );
  }
);

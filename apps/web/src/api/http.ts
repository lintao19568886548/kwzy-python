import axios from "axios";
import { useAuthStore } from "@/stores/auth";

export const http = axios.create({
  baseURL: "/api/v1",
  timeout: 20000,
});

http.interceptors.request.use((config) => {
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
  (err) => {
    const msg =
      err?.response?.data?.message ||
      err?.response?.data?.code ||
      err.message ||
      "网络错误";
    return Promise.reject(new Error(msg));
  }
);

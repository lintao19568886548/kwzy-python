import { describe, expect, it, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useAuthStore } from "./auth";

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("can checks star and explicit permissions", () => {
    const auth = useAuthStore();
    auth.permissions = ["*"];
    expect(auth.can("lead:read")).toBe(true);
    auth.permissions = ["lead:read"];
    expect(auth.can("lead:read")).toBe(true);
    expect(auth.can("lead:write")).toBe(false);
    expect(auth.can(["lead:read", "lead:write"])).toBe(false);
  });

  it("clearSession removes tokens", () => {
    const auth = useAuthStore();
    auth.accessToken = "a";
    auth.permissions = ["*"];
    auth.clearSession();
    expect(auth.accessToken).toBe("");
    expect(localStorage.getItem("kwzy_access_token")).toBeNull();
    expect(localStorage.getItem("kwzy_refresh_token")).toBeNull();
  });
});

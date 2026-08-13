import { describe, expect, it, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useAuthStore } from "@/stores/auth";
import { hasPermission } from "./permission";

describe("permission helper", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("allows star", () => {
    useAuthStore().permissions = ["*"];
    expect(hasPermission("work_order:write")).toBe(true);
  });

  it("requires all codes", () => {
    useAuthStore().permissions = ["a", "b"];
    expect(hasPermission(["a", "b"])).toBe(true);
    expect(hasPermission(["a", "c"])).toBe(false);
  });
});

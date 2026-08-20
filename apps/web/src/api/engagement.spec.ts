import { beforeEach, describe, expect, it, vi } from "vitest";

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("@/api/http", () => ({ http: { get } }));

import {
  engagementIdempotencyHeaders,
  fetchEngagementWorkspace,
} from "@/api/engagement";

describe("engagement workspace client", () => {
  beforeEach(() => {
    get.mockReset();
    get.mockImplementation((url: string) => {
      if (url === "/engagement/overview") {
        return Promise.resolve({
          data: {
            data: {
              published_policies: 1,
              published_services: 2,
              open_service_cases: 3,
              published_activities: 4,
              published_announcements: 5,
              truth: { production_contacted: false },
            },
          },
        });
      }
      return Promise.resolve({ data: { data: [] } });
    });
  });

  it("loads only staff projections in staff mode", async () => {
    const result = await fetchEngagementWorkspace("staff");
    expect(result.overview.published_policies).toBe(1);
    expect(result.inbox).toEqual([]);
    expect(get).toHaveBeenCalledWith("/engagement/staff/policies");
    expect(get).toHaveBeenCalledWith("/engagement/staff/service-cases");
    expect(get).not.toHaveBeenCalledWith("/engagement/tenant/announcement-inbox");
  });

  it("loads persisted tenant projections and inbox in tenant mode", async () => {
    await fetchEngagementWorkspace("tenant");
    expect(get).toHaveBeenCalledWith("/engagement/tenant/policies");
    expect(get).toHaveBeenCalledWith("/engagement/tenant/activity-registrations");
    expect(get).toHaveBeenCalledWith("/engagement/tenant/announcement-inbox");
  });

  it("generates bounded command keys", () => {
    const value = engagementIdempotencyHeaders("pc-engagement")["Idempotency-Key"];
    expect(value).toMatch(/^pc-engagement-/);
    expect(value.length).toBeLessThanOrEqual(128);
  });
});

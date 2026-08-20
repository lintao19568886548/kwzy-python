import { http } from "@/api/http";
import type { Envelope } from "@/api/types";

export type EngagementMode = "staff" | "tenant";
export type EngagementOverview = {
  published_policies: number;
  published_services: number;
  open_service_cases: number;
  published_activities: number;
  published_announcements: number;
  truth: Record<string, string | boolean>;
};
export type VersionBase = {
  id: number;
  version: number;
  status: string;
  checksum: string;
  created_at: string;
  published_at: string | null;
};
export type Policy = {
  id: number;
  park_id: number | null;
  code: string;
  status: string;
  current_version: number;
  published_version: number | null;
  lock_version: number;
  version: VersionBase & {
    title: string;
    summary: string | null;
    category: string;
    source_publisher: string;
    source_url: string | null;
    effective_on: string | null;
    expires_on: string | null;
    applicability: Array<Record<string, unknown>>;
  };
};
export type ServiceCatalog = {
  id: number;
  park_id: number;
  code: string;
  status: string;
  current_version: number;
  published_version: number | null;
  lock_version: number;
  version: VersionBase & {
    title: string;
    description: string;
    provider: {
      type: string;
      name: string;
      state: string;
      connected: boolean;
    };
    sla_hours: number;
    appointment_required: boolean;
    price: {
      amount: string | null;
      currency: string;
      payment_available: boolean;
    };
  };
};
export type ServiceCase = {
  id: number;
  case_no: string;
  park_id: number;
  catalog_id: number;
  party_id: number;
  status: string;
  priority: string;
  subject: string;
  description: string;
  contact_masked: string | null;
  assigned_to: number | null;
  appointment_at: string | null;
  result_summary: string | null;
  sla_due_at: string;
  lock_version: number;
  events: Array<{ id: number; event_type: string; note: string | null; occurred_at: string }>;
};
export type Activity = {
  id: number;
  park_id: number;
  code: string;
  status: string;
  current_version: number;
  published_version: number | null;
  lock_version: number;
  version: VersionBase & {
    title: string;
    description: string;
    location: string;
    starts_at: string;
    ends_at: string;
    registration_opens_at: string;
    registration_closes_at: string;
    capacity: number;
    confirmed_count: number;
    waitlist_count: number;
    cancellation_terms: string;
  };
};
export type ActivityRegistration = {
  id: number;
  activity_id: number;
  activity_version_id: number;
  party_id: number;
  status: string;
  attendee_count: number;
  waitlist_position: number | null;
  lock_version: number;
  checked_in_at: string | null;
};
export type Announcement = {
  id: number;
  park_id: number | null;
  code: string;
  status: string;
  current_version: number;
  published_version: number | null;
  lock_version: number;
  version: VersionBase & {
    title: string;
    content_text: string;
    priority: string;
    publish_at: string;
    expires_at: string | null;
    audience: Array<Record<string, unknown>>;
  };
};
export type AnnouncementInboxItem = {
  delivery_id: number;
  announcement_id: number;
  version: number;
  title: string;
  content_text: string;
  priority: string;
  status: string;
  delivered_at: string | null;
  read_at: string | null;
  audience_snapshot: Record<string, unknown>;
};

export type EngagementWorkspace = {
  overview: EngagementOverview;
  policies: Policy[];
  services: ServiceCatalog[];
  cases: ServiceCase[];
  activities: Activity[];
  registrations: ActivityRegistration[];
  announcements: Announcement[];
  inbox: AnnouncementInboxItem[];
};

export async function fetchEngagementWorkspace(
  mode: EngagementMode
): Promise<EngagementWorkspace> {
  const scope = mode === "staff" ? "staff" : "tenant";
  const responses = await Promise.all([
    http.get<Envelope<EngagementOverview>>("/engagement/overview"),
    http.get<Envelope<Policy[]>>(`/engagement/${scope}/policies`),
    http.get<Envelope<ServiceCatalog[]>>(`/engagement/${scope}/services`),
    http.get<Envelope<ServiceCase[]>>(`/engagement/${scope}/service-cases`),
    http.get<Envelope<Activity[]>>(`/engagement/${scope}/activities`),
    http.get<Envelope<ActivityRegistration[]>>(
      `/engagement/${scope}/activity-registrations`
    ),
    http.get<Envelope<Announcement[]>>(`/engagement/${scope}/announcements`),
    mode === "tenant"
      ? http.get<Envelope<AnnouncementInboxItem[]>>("/engagement/tenant/announcement-inbox")
      : Promise.resolve({ data: { data: [] as AnnouncementInboxItem[] } }),
  ]);
  return {
    overview: responses[0].data.data,
    policies: responses[1].data.data,
    services: responses[2].data.data,
    cases: responses[3].data.data,
    activities: responses[4].data.data,
    registrations: responses[5].data.data,
    announcements: responses[6].data.data,
    inbox: responses[7].data.data,
  };
}

export function engagementIdempotencyHeaders(prefix: string) {
  return { "Idempotency-Key": `${prefix}-${crypto.randomUUID()}` };
}

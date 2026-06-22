// API client for the FastAPI backend. All counting comes from the backend engine.

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Person = { id: number; code: string; name: string };

export type Counter = {
  key: string;
  label: string;
  country: string;
  mode: "target_to_reach" | "limit_to_watch";
  window: "calendar_year" | "financial_year";
  windowStart: string;
  windowEnd: string;
  count: number;
  threshold: number;
  pending: number | null;
  remainingBeforeLimit: number | null;
  warnLevel: "green" | "amber" | "red" | "reached" | "progress" | "neutral";
  allowance: number | null;
};

export type Summary = {
  asOf: string;
  counters: Counter[];
  travelDays: number;
  unknownDays: number;
  incomplete: boolean;
  settings: { defaultTripLen: number; minGapDays: number };
};

export type CalendarDay = {
  date: string;
  status: "india" | "uae" | "both" | "unknown" | "future";
  countries: string[];
};

export type Entry = {
  id: number;
  country: string;
  from_date: string;
  to_date: string;
  source: string;
  note: string;
};

export type Suggestion = {
  country: string;
  from: string;
  to: string;
  days: number;
  pendingAfter: number;
};

export type Trip = {
  id: number;
  country: string;
  from_date: string;
  to_date: string;
  status: string;
};

export type CounterConfig = {
  id: number;
  key: string;
  label: string;
  country: string;
  mode: string;
  threshold: number;
  window: string;
};

export type AppSettings = {
  person_id: number;
  default_trip_len: number;
  min_gap_days: number;
};

export type TicketSegment = {
  date: string | null;
  from_airport: string;
  to_airport: string;
  from_country: "IN" | "AE" | "OTHER";
  to_country: "IN" | "AE" | "OTHER";
  airline?: string;
  flight_no: string;
  confidence?: number;
};

export type TicketAnalysis = {
  results: { filename: string; error?: string; segments: TicketSegment[] }[];
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  persons: () => req<Person[]>("/persons"),
  summary: (pid: number, asOf?: string) =>
    req<Summary>(`/persons/${pid}/summary${asOf ? `?as_of=${asOf}` : ""}`),
  calendar: (pid: number, month: string, asOf?: string) =>
    req<{ month: string; days: CalendarDay[] }>(
      `/persons/${pid}/calendar?month=${month}${asOf ? `&as_of=${asOf}` : ""}`
    ),
  entries: (pid: number) => req<Entry[]>(`/persons/${pid}/entries`),
  createEntry: (pid: number, body: { country: string; from_date: string; to_date: string; note?: string }) =>
    req<Entry>(`/persons/${pid}/entries`, { method: "POST", body: JSON.stringify(body) }),
  deleteEntry: (id: number) => req<void>(`/entries/${id}`, { method: "DELETE" }),
  analyzeTickets: async (pid: number, files: File[]): Promise<TicketAnalysis> => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const res = await fetch(`${BASE}/persons/${pid}/tickets/analyze`, {
      method: "POST",
      body: form, // no Content-Type header — browser sets multipart boundary
    });
    if (!res.ok) throw new Error(`${res.status}: ${await res.text().catch(() => "")}`);
    return res.json();
  },
  commitTickets: (pid: number, segments: TicketSegment[]) =>
    req<{ created: number }>(`/persons/${pid}/tickets/commit`, {
      method: "POST",
      body: JSON.stringify({ segments }),
    }),
  suggestions: (pid: number, asOf?: string) =>
    req<{ pending: number; trips: Suggestion[] }>(
      `/persons/${pid}/suggestions${asOf ? `?as_of=${asOf}` : ""}`
    ),
  trips: (pid: number) => req<Trip[]>(`/persons/${pid}/trips`),
  acceptTrip: (pid: number, body: { country?: string; from_date: string; to_date: string }) =>
    req<Trip>(`/persons/${pid}/trips`, { method: "POST", body: JSON.stringify(body) }),
  deleteTrip: (id: number) => req<void>(`/trips/${id}`, { method: "DELETE" }),
  counters: (pid: number) => req<CounterConfig[]>(`/persons/${pid}/counters`),
  updateCounter: (pid: number, key: string, body: Omit<CounterConfig, "id">) =>
    req<CounterConfig>(`/persons/${pid}/counters/${key}`, { method: "PUT", body: JSON.stringify(body) }),
  settings: (pid: number) => req<AppSettings>(`/persons/${pid}/settings`),
  updateSettings: (pid: number, body: { default_trip_len: number; min_gap_days: number }) =>
    req<AppSettings>(`/persons/${pid}/settings`, { method: "PUT", body: JSON.stringify(body) }),
};

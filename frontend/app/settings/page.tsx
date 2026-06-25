"use client";

import * as React from "react";
import { useProfile } from "@/components/profile-context";
import {
  api,
  type AppSettings,
  type CounterConfig,
  type GoogleStatus,
  type GoogleSyncResult,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const inputCls =
  "h-9 w-full rounded-lg border border-border bg-card px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30";

export default function SettingsPage() {
  const { current } = useProfile();
  const [counters, setCounters] = React.useState<CounterConfig[]>([]);
  const [settings, setSettings] = React.useState<AppSettings | null>(null);
  const [msg, setMsg] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    if (!current) return;
    Promise.all([api.counters(current.id), api.settings(current.id)]).then(([c, s]) => {
      setCounters(c);
      setSettings(s);
    });
  }, [current]);

  React.useEffect(() => {
    load();
  }, [load]);

  if (!current || !settings) return null;

  function patchCounter(key: string, patch: Partial<CounterConfig>) {
    setCounters((prev) => prev.map((c) => (c.key === key ? { ...c, ...patch } : c)));
  }

  async function saveCounter(c: CounterConfig) {
    if (!current) return;
    const { id, ...body } = c;
    await api.updateCounter(current.id, c.key, body);
    setMsg(`${c.label} updated ✓`);
    load();
  }

  async function saveSettings() {
    if (!current) return;
    await api.updateSettings(current.id, {
      default_trip_len: settings!.default_trip_len,
      min_gap_days: settings!.min_gap_days,
    });
    setMsg("Trip settings updated ✓");
  }

  return (
    <div className="space-y-6">
      {msg && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-sm text-emerald-700">
          {msg}
        </div>
      )}

      {/* Google Calendar sync is enabled for NKA only. */}
      {current.code === "NKA" && <GoogleCalendarCard personId={current.id} />}

      {counters.map((c) => (
        <Card key={c.key}>
          <CardHeader>
            <CardTitle>{c.label} counter</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Mode</label>
                <select className={inputCls} value={c.mode} onChange={(e) => patchCounter(c.key, { mode: e.target.value })}>
                  <option value="target_to_reach">Target to reach</option>
                  <option value="limit_to_watch">Limit to watch</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Threshold</label>
                <input
                  type="number"
                  className={inputCls}
                  value={c.threshold}
                  onChange={(e) => patchCounter(c.key, { threshold: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Window</label>
                <select className={inputCls} value={c.window} onChange={(e) => patchCounter(c.key, { window: e.target.value })}>
                  <option value="calendar_year">Calendar year</option>
                  <option value="financial_year">Financial year (Apr–Mar)</option>
                </select>
              </div>
              <div className="flex items-end">
                <Button size="sm" onClick={() => saveCounter(c)}>
                  Save
                </Button>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Country: {c.country === "AE" ? "🇦🇪 UAE" : "🇮🇳 India"} · key: {c.key}
            </p>
          </CardContent>
        </Card>
      ))}

      <Card>
        <CardHeader>
          <CardTitle>Trip suggestion settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Default trip length (days)</label>
              <input
                type="number"
                className={inputCls}
                value={settings.default_trip_len}
                onChange={(e) => setSettings({ ...settings, default_trip_len: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Min gap between trips (days)</label>
              <input
                type="number"
                className={inputCls}
                value={settings.min_gap_days}
                onChange={(e) => setSettings({ ...settings, min_gap_days: Number(e.target.value) })}
              />
            </div>
            <div className="flex items-end">
              <Button size="sm" onClick={saveSettings}>
                Save
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function GoogleCalendarCard({ personId }: { personId: number }) {
  const [status, setStatus] = React.useState<GoogleStatus | null>(null);
  const [result, setResult] = React.useState<GoogleSyncResult | null>(null);
  const [note, setNote] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const loadStatus = React.useCallback(() => {
    api.googleStatus(personId).then(setStatus).catch(() => setStatus(null));
  }, [personId]);

  React.useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Surface the ?gcal=connected|error result of the OAuth redirect, then clean the URL.
  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const g = params.get("gcal");
    if (!g) return;
    setNote(
      g === "connected"
        ? "Google Calendar connected ✓ — hit “Sync now” to import your events."
        : "Could not connect Google Calendar. Please try again."
    );
    window.history.replaceState({}, "", window.location.pathname);
    loadStatus();
  }, [loadStatus]);

  async function connect() {
    setBusy(true);
    setNote(null);
    try {
      const { url } = await api.googleAuthUrl(personId);
      window.location.href = url; // leave the app for Google's consent screen
    } catch (e) {
      setNote(`Connect failed: ${(e as Error).message}`);
      setBusy(false);
    }
  }

  async function sync() {
    setBusy(true);
    setNote(null);
    setResult(null);
    try {
      const r = await api.googleSync(personId);
      setResult(r);
      loadStatus();
    } catch (e) {
      setNote(`Sync failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    try {
      await api.googleDisconnect(personId);
      setResult(null);
      loadStatus();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Google Calendar</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {note && (
          <div className="rounded-lg border border-sky-200 bg-sky-50 p-2 text-sm text-sky-700">
            {note}
          </div>
        )}

        {status === null ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !status.configured ? (
          <p className="text-sm text-muted-foreground">
            Google sync isn’t set up on the server yet. Add{" "}
            <code>GOOGLE_CLIENT_ID</code>, <code>GOOGLE_CLIENT_SECRET</code> and{" "}
            <code>GOOGLE_REDIRECT_URI</code> to the backend, then refresh.
          </p>
        ) : status.connected ? (
          <>
            <p className="text-sm">
              Connected{status.email ? ` as ${status.email}` : ""}.{" "}
              {status.last_synced && (
                <span className="text-muted-foreground">
                  Last synced {new Date(status.last_synced).toLocaleString()}.
                </span>
              )}
            </p>
            <p className="text-xs text-muted-foreground">
              Sync imports all-day trips tagged with a country as <b>travel days</b>, and
              weddings/holidays/functions as <b>commitments</b>. Re-syncing won’t create
              duplicates.
            </p>
            <div className="flex gap-2">
              <Button size="sm" onClick={sync} disabled={busy}>
                {busy ? "Syncing…" : "Sync now"}
              </Button>
              <Button size="sm" variant="ghost" onClick={disconnect} disabled={busy}>
                Disconnect
              </Button>
            </div>
            {result && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-sm text-emerald-700">
                Imported {result.entries_created} travel day-range
                {result.entries_created === 1 ? "" : "s"} and {result.events_created} commitment
                {result.events_created === 1 ? "" : "s"}
                {result.entries_updated + result.events_updated > 0 &&
                  `, updated ${result.entries_updated + result.events_updated}`}
                . Scanned {result.scanned} events ({result.skipped} skipped).
              </div>
            )}
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              Connect a Google account to automatically import past and upcoming trips and
              commitments from its calendar.
            </p>
            <Button size="sm" onClick={connect} disabled={busy}>
              {busy ? "Redirecting…" : "Connect Google Calendar"}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}

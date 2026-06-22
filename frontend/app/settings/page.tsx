"use client";

import * as React from "react";
import { useProfile } from "@/components/profile-context";
import { api, type AppSettings, type CounterConfig } from "@/lib/api";
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

"use client";

import * as React from "react";
import { Check, Plane } from "lucide-react";
import { useProfile } from "@/components/profile-context";
import { api, type Suggestion, type Trip } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function TripsPage() {
  const { current } = useProfile();
  const [pending, setPending] = React.useState(0);
  const [suggestions, setSuggestions] = React.useState<Suggestion[]>([]);
  const [accepted, setAccepted] = React.useState<Trip[]>([]);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  const load = React.useCallback(() => {
    if (!current) return;
    setLoading(true);
    Promise.all([api.suggestions(current.id), api.trips(current.id)])
      .then(([s, t]) => {
        setPending(s.pending);
        setSuggestions(s.trips);
        setAccepted(t);
      })
      .finally(() => setLoading(false));
  }, [current]);

  React.useEffect(() => {
    load();
  }, [load]);

  if (!current) return null;

  async function accept(s: Suggestion) {
    if (!current) return;
    setBusy(`${s.from}-${s.to}`);
    try {
      await api.acceptTrip(current.id, { country: s.country, from_date: s.from, to_date: s.to });
      load();
    } finally {
      setBusy(null);
    }
  }

  async function removeTrip(id: number) {
    await api.deleteTrip(id);
    load();
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>
            <Plane className="mr-1 inline h-4 w-4" /> Suggested Dubai Trips
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-muted-foreground">
            You currently have <b>{pending}</b> Dubai days pending. The schedule below is
            designed to close the target. Accepting a trip adds it to your counts.
          </p>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : suggestions.length === 0 ? (
            <p className="text-sm text-emerald-600">
              {pending === 0
                ? "Target already achieved — no trips needed 🎉"
                : "No more trips fit within this window."}
            </p>
          ) : (
            <ul className="space-y-2">
              {suggestions.map((s, i) => (
                <li
                  key={`${s.from}-${i}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <div>
                    <span className="font-medium">Trip {i + 1}: 🇦🇪 {s.from} → {s.to}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {s.days} days · after: {s.pendingAfter} pending
                    </span>
                  </div>
                  <Button size="sm" disabled={busy === `${s.from}-${s.to}`} onClick={() => accept(s)}>
                    <Check className="h-3.5 w-3.5" /> Accept
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Accepted Trips ({accepted.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {accepted.length === 0 ? (
            <p className="text-sm text-muted-foreground">No accepted trips yet.</p>
          ) : (
            <ul className="space-y-2">
              {accepted.map((t) => (
                <li key={t.id} className="flex items-center justify-between rounded-lg bg-muted px-3 py-2 text-sm">
                  <span>🇦🇪 {t.from_date} → {t.to_date}</span>
                  <Button variant="ghost" size="sm" onClick={() => removeTrip(t.id)}>
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

"use client";

import * as React from "react";
import { useProfile } from "@/components/profile-context";
import { api, type Entry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TicketUploader } from "@/components/ticket-uploader";

export default function EntryPage() {
  const { current } = useProfile();
  const [country, setCountry] = React.useState("AE");
  const [from, setFrom] = React.useState("");
  const [to, setTo] = React.useState("");
  const [note, setNote] = React.useState("");
  const [entries, setEntries] = React.useState<Entry[]>([]);
  const [msg, setMsg] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(() => {
    if (!current) return;
    api.entries(current.id).then(setEntries);
  }, [current]);

  React.useEffect(() => {
    load();
  }, [load]);

  if (!current) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!current) return;
    setMsg(null);
    if (!from || !to) {
      setMsg("Both From and To dates are required.");
      return;
    }
    if (to < from) {
      setMsg("To date cannot be before From date.");
      return;
    }
    setBusy(true);
    try {
      await api.createEntry(current.id, { country, from_date: from, to_date: to, note });
      setMsg("Saved ✓");
      setFrom("");
      setTo("");
      setNote("");
      load();
    } catch (err: any) {
      setMsg(`Error: ${err.message ?? err}`);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    await api.deleteEntry(id);
    load();
  }

  const inputCls =
    "h-9 w-full rounded-lg border border-border bg-card px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30";

  return (
    <div className="space-y-6">
      <TicketUploader personId={current.id} onCommitted={load} />
      <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Manual Entry (range — endpoints inclusive)</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Country</label>
              <select className={inputCls} value={country} onChange={(e) => setCountry(e.target.value)}>
                <option value="AE">🇦🇪 Dubai / UAE</option>
                <option value="IN">🇮🇳 India</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">From</label>
                <input type="date" className={inputCls} value={from} onChange={(e) => setFrom(e.target.value)} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">To</label>
                <input type="date" className={inputCls} value={to} onChange={(e) => setTo(e.target.value)} />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Note (optional)</label>
              <input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save Entry"}
            </Button>
            {msg && <p className="text-sm text-muted-foreground">{msg}</p>}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Existing entries ({entries.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {entries.length === 0 ? (
            <p className="text-sm text-muted-foreground">No entries yet.</p>
          ) : (
            <ul className="space-y-2">
              {entries.map((e) => (
                <li key={e.id} className="flex items-center justify-between rounded-lg bg-muted px-3 py-2 text-sm">
                  <span>
                    {e.country === "AE" ? "🇦🇪" : "🇮🇳"} {e.from_date} → {e.to_date}
                    {e.note && <span className="ml-2 text-xs text-muted-foreground">{e.note}</span>}
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => remove(e.id)}>
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      </div>
    </div>
  );
}

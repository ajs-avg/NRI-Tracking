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
  const [editId, setEditId] = React.useState<number | null>(null);
  const [ef, setEf] = React.useState({ country: "AE", from_date: "", to_date: "", arr_time: "", note: "" });

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

  function startEdit(e: Entry) {
    setEditId(e.id);
    setEf({
      country: e.country,
      from_date: e.from_date,
      to_date: e.to_date,
      arr_time: e.arr_time ?? "",
      note: e.note ?? "",
    });
  }

  async function saveEdit(id: number) {
    if (ef.to_date < ef.from_date) {
      setMsg("To date cannot be before From date.");
      return;
    }
    setBusy(true);
    try {
      await api.updateEntry(id, {
        country: ef.country,
        from_date: ef.from_date,
        to_date: ef.to_date,
        arr_time: ef.arr_time || null,
        note: ef.note,
      });
      setEditId(null);
      load();
    } catch (err: any) {
      setMsg(`Error: ${err.message ?? err}`);
    } finally {
      setBusy(false);
    }
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
              {entries.map((e) =>
                editId === e.id ? (
                  <li key={e.id} className="space-y-2 rounded-lg bg-muted px-3 py-2 text-sm">
                    <div className="grid grid-cols-2 gap-2">
                      <select className={inputCls} value={ef.country} onChange={(ev) => setEf({ ...ef, country: ev.target.value })}>
                        <option value="AE">🇦🇪 Dubai</option>
                        <option value="IN">🇮🇳 India</option>
                      </select>
                      <input type="time" className={inputCls} value={ef.arr_time} onChange={(ev) => setEf({ ...ef, arr_time: ev.target.value })} title="Arrival time" />
                      <input type="date" className={inputCls} value={ef.from_date} onChange={(ev) => setEf({ ...ef, from_date: ev.target.value })} />
                      <input type="date" className={inputCls} value={ef.to_date} onChange={(ev) => setEf({ ...ef, to_date: ev.target.value })} />
                    </div>
                    <input className={inputCls} placeholder="Note" value={ef.note} onChange={(ev) => setEf({ ...ef, note: ev.target.value })} />
                    <div className="flex gap-2">
                      <Button size="sm" disabled={busy} onClick={() => saveEdit(e.id)}>Save</Button>
                      <Button variant="ghost" size="sm" onClick={() => setEditId(null)}>Cancel</Button>
                    </div>
                  </li>
                ) : (
                  <li key={e.id} className="flex items-center justify-between rounded-lg bg-muted px-3 py-2 text-sm">
                    <span>
                      {e.country === "AE" ? "🇦🇪" : "🇮🇳"} {e.from_date} → {e.to_date}
                      {e.arr_time && <span className="ml-2 text-xs text-muted-foreground">⏱ {e.arr_time}</span>}
                      {e.note && <span className="ml-2 text-xs text-muted-foreground">{e.note}</span>}
                    </span>
                    <span className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => startEdit(e)}>Edit</Button>
                      <Button variant="ghost" size="sm" onClick={() => remove(e.id)}>Delete</Button>
                    </span>
                  </li>
                )
              )}
            </ul>
          )}
        </CardContent>
      </Card>
      </div>
    </div>
  );
}

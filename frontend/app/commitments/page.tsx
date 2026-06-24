"use client";

import * as React from "react";
import { Check, Upload, X } from "lucide-react";
import { useProfile } from "@/components/profile-context";
import { api, type CommitmentEvent, type EventType } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const inputCls =
  "h-9 w-full rounded-lg border border-border bg-card px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30";

const TYPE_META: Record<EventType, { label: string; cls: string }> = {
  mandatory: { label: "Mandatory", cls: "bg-orange-50 text-orange-700" },
  travel_opportunity: { label: "Travel window", cls: "bg-emerald-50 text-emerald-700" },
  optional: { label: "Optional", cls: "bg-zinc-100 text-zinc-600" },
};

const emptyForm = {
  title: "",
  country: "IN",
  from_date: "",
  to_date: "",
  event_type: "mandatory" as EventType,
  note: "",
};

export default function CommitmentsPage() {
  const { current } = useProfile();
  const [events, setEvents] = React.useState<CommitmentEvent[]>([]);
  const [form, setForm] = React.useState({ ...emptyForm });
  const [editId, setEditId] = React.useState<number | null>(null);
  const [msg, setMsg] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(() => {
    if (!current) return;
    api.events(current.id).then(setEvents);
  }, [current]);

  React.useEffect(() => {
    load();
  }, [load]);

  if (!current) return null;

  const today = new Date().toISOString().slice(0, 10);
  const unanswered = events.filter((e) => e.attend === null && e.to_date >= today);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!current) return;
    setMsg(null);
    if (!form.title || !form.from_date) {
      setMsg("Title and start date are required.");
      return;
    }
    const to = form.to_date || form.from_date;
    if (to < form.from_date) {
      setMsg("End date cannot be before start date.");
      return;
    }
    setBusy(true);
    try {
      const body = { ...form, to_date: to };
      if (editId) await api.updateEvent(editId, body);
      else await api.createEvent(current.id, body);
      setForm({ ...emptyForm });
      setEditId(null);
      load();
    } catch (err: any) {
      setMsg(`Error: ${err.message ?? err}`);
    } finally {
      setBusy(false);
    }
  }

  function startEdit(ev: CommitmentEvent) {
    setEditId(ev.id);
    setForm({
      title: ev.title,
      country: ev.country,
      from_date: ev.from_date,
      to_date: ev.to_date,
      event_type: ev.event_type,
      note: ev.note,
    });
  }

  async function setAttend(id: number, attend: boolean | null) {
    await api.updateEvent(id, { attend });
    load();
  }

  async function remove(id: number) {
    await api.deleteEvent(id);
    if (editId === id) {
      setEditId(null);
      setForm({ ...emptyForm });
    }
    load();
  }

  async function importCsv(e: React.ChangeEvent<HTMLInputElement>) {
    if (!current) return;
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setMsg("Importing CSV…");
    try {
      const res = await api.importEvents(current.id, file);
      setMsg(`Imported ${res.created} event(s).${res.errors.length ? ` Skipped: ${res.errors.join("; ")}` : ""}`);
      load();
    } catch (err: any) {
      setMsg(`Error: ${err.message ?? err}`);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  return (
    <div className="space-y-6">
      {unanswered.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Upcoming — will you attend?</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {unanswered.map((ev) => (
                <li key={ev.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm">
                  <span>
                    {ev.country === "AE" ? "🇦🇪" : "🇮🇳"} <b>{ev.title}</b>{" "}
                    <span className="text-xs text-muted-foreground">{ev.from_date} → {ev.to_date}</span>
                  </span>
                  <span className="flex gap-1">
                    <Button size="sm" onClick={() => setAttend(ev.id, true)}>
                      <Check className="h-3.5 w-3.5" /> Attend
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setAttend(ev.id, false)}>
                      <X className="h-3.5 w-3.5" /> Skip
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{editId ? "Edit commitment" : "Add commitment"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Title</label>
                <input className={inputCls} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. School annual day" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">Location</label>
                  <select className={inputCls} value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })}>
                    <option value="IN">🇮🇳 India</option>
                    <option value="AE">🇦🇪 Dubai / UAE</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">Type</label>
                  <select className={inputCls} value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value as EventType })}>
                    <option value="mandatory">Mandatory (must be there)</option>
                    <option value="travel_opportunity">Travel window (holidays)</option>
                    <option value="optional">Optional</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">From</label>
                  <input type="date" className={inputCls} value={form.from_date} onChange={(e) => setForm({ ...form, from_date: e.target.value })} />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">To (optional)</label>
                  <input type="date" className={inputCls} value={form.to_date} onChange={(e) => setForm({ ...form, to_date: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Note (optional)</label>
                <input className={inputCls} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={busy}>{busy ? "Saving…" : editId ? "Update" : "Add"}</Button>
                {editId && (
                  <Button type="button" variant="ghost" onClick={() => { setEditId(null); setForm({ ...emptyForm }); }}>Cancel</Button>
                )}
              </div>
              <div className="border-t border-border pt-3">
                <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-sm hover:bg-muted">
                  <Upload className="h-4 w-4" /> Import CSV
                  <input type="file" accept=".csv,text/csv" className="hidden" onChange={importCsv} />
                </label>
                <p className="mt-1 text-xs text-muted-foreground">
                  Columns: title, country, from, to, type, attend, note. (Export the merged sheet as CSV.)
                </p>
              </div>
              {msg && <p className="text-sm text-muted-foreground">{msg}</p>}
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Commitments ({events.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No commitments yet.</p>
            ) : (
              <ul className="space-y-2">
                {events.map((ev) => (
                  <li key={ev.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
                    <span>
                      {ev.country === "AE" ? "🇦🇪" : ev.country === "IN" ? "🇮🇳" : "🌐"} <b>{ev.title}</b>{" "}
                      <span className="text-xs text-muted-foreground">{ev.from_date} → {ev.to_date}</span>
                      <span className={`ml-2 rounded px-1.5 py-0.5 text-[10px] ${TYPE_META[ev.event_type].cls}`}>{TYPE_META[ev.event_type].label}</span>
                      {ev.attend === true && <span className="ml-1 text-[10px] text-emerald-600">✓ attending</span>}
                      {ev.attend === false && <span className="ml-1 text-[10px] text-zinc-400">skipped</span>}
                    </span>
                    <span className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => startEdit(ev)}>Edit</Button>
                      <Button variant="ghost" size="sm" onClick={() => remove(ev.id)}>Delete</Button>
                    </span>
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

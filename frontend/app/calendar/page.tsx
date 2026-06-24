"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useProfile } from "@/components/profile-context";
import { api, type CalendarDay, type Entry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const STATUS_META: Record<CalendarDay["status"], { label: string; cls: string; flag: string }> = {
  uae: { label: "Dubai", cls: "bg-emerald-50 text-emerald-700", flag: "🇦🇪" },
  india: { label: "India", cls: "bg-orange-50 text-orange-700", flag: "🇮🇳" },
  both: { label: "Travel", cls: "bg-violet-50 text-violet-700", flag: "🇮🇳🇦🇪" },
  unknown: { label: "Unknown", cls: "bg-zinc-100 text-zinc-500", flag: "?" },
  future: { label: "—", cls: "bg-card text-zinc-300", flag: "" },
};

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function ymd(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function CalendarPage() {
  const { current } = useProfile();
  const [cursor, setCursor] = React.useState(() => new Date());
  const [days, setDays] = React.useState<CalendarDay[]>([]);
  const [selected, setSelected] = React.useState<string | null>(null);
  const [entries, setEntries] = React.useState<Entry[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [editId, setEditId] = React.useState<number | null>(null);
  const [ef, setEf] = React.useState({ country: "AE", from_date: "", to_date: "", arr_time: "" });

  const month = ymd(cursor);

  const load = React.useCallback(() => {
    if (!current) return;
    setLoading(true);
    Promise.all([api.calendar(current.id, month), api.entries(current.id)])
      .then(([cal, ents]) => {
        setDays(cal.days);
        setEntries(ents);
      })
      .finally(() => setLoading(false));
  }, [current, month]);

  React.useEffect(() => {
    load();
  }, [load]);

  if (!current) return null;

  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  // JS getDay(): 0=Sun..6=Sat. Convert to Mon-first offset.
  const leadBlanks = (first.getDay() + 6) % 7;

  const selectedEntries = selected
    ? entries.filter((e) => e.from_date <= selected && e.to_date >= selected)
    : [];

  async function quickAdd(country: string) {
    if (!current || !selected) return;
    await api.createEntry(current.id, { country, from_date: selected, to_date: selected });
    load();
    const refreshed = await api.calendar(current.id, month);
    setDays(refreshed.days);
  }

  async function removeEntry(id: number) {
    await api.deleteEntry(id);
    load();
  }

  function startEdit(e: Entry) {
    setEditId(e.id);
    setEf({ country: e.country, from_date: e.from_date, to_date: e.to_date, arr_time: e.arr_time ?? "" });
  }

  async function saveEdit(id: number) {
    if (ef.to_date < ef.from_date) return;
    await api.updateEntry(id, {
      country: ef.country,
      from_date: ef.from_date,
      to_date: ef.to_date,
      arr_time: ef.arr_time || null,
    });
    setEditId(null);
    load();
  }

  const monthLabel = cursor.toLocaleString("en-US", { month: "long", year: "numeric" });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{monthLabel}</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => setCursor(new Date())}>
            Today
          </Button>
          <Button variant="outline" size="icon" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        {(["uae", "india", "both", "unknown"] as const).map((s) => (
          <span key={s} className="inline-flex items-center gap-1">
            <span className={cn("rounded px-1.5 py-0.5", STATUS_META[s].cls)}>{STATUS_META[s].flag}</span>
            {STATUS_META[s].label}
          </span>
        ))}
      </div>

      <Card className="p-3">
        <div className="grid grid-cols-7 gap-1">
          {WEEKDAYS.map((w) => (
            <div key={w} className="pb-1 text-center text-[11px] font-medium text-muted-foreground">
              {w}
            </div>
          ))}
          {Array.from({ length: leadBlanks }).map((_, i) => (
            <div key={`b${i}`} />
          ))}
          {days.map((d) => {
            const meta = STATUS_META[d.status];
            const day = Number(d.date.slice(-2));
            return (
              <button
                key={d.date}
                onClick={() => setSelected(d.date)}
                className={cn(
                  "flex aspect-square flex-col items-center justify-center rounded-lg border border-transparent text-xs transition hover:border-border",
                  meta.cls,
                  selected === d.date && "ring-2 ring-primary"
                )}
              >
                <span className="font-medium">{day}</span>
                <span className="text-sm leading-none">{meta.flag}</span>
              </button>
            );
          })}
        </div>
        {loading && <p className="pt-2 text-xs text-muted-foreground">Loading…</p>}
      </Card>

      {selected && (
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold">{selected}</h3>
            <Button variant="ghost" size="icon" onClick={() => setSelected(null)}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {selectedEntries.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No data for this day (UNKNOWN). Quick add:
            </p>
          ) : (
            <ul className="mb-3 space-y-2">
              {selectedEntries.map((e) =>
                editId === e.id ? (
                  <li key={e.id} className="space-y-2 rounded-lg bg-muted px-3 py-2 text-sm">
                    <div className="grid grid-cols-2 gap-2">
                      <select className="h-8 rounded-md border border-border bg-card px-2 text-xs" value={ef.country} onChange={(ev) => setEf({ ...ef, country: ev.target.value })}>
                        <option value="AE">🇦🇪 Dubai</option>
                        <option value="IN">🇮🇳 India</option>
                      </select>
                      <input type="time" className="h-8 rounded-md border border-border bg-card px-2 text-xs" value={ef.arr_time} onChange={(ev) => setEf({ ...ef, arr_time: ev.target.value })} title="Arrival time" />
                      <input type="date" className="h-8 rounded-md border border-border bg-card px-2 text-xs" value={ef.from_date} onChange={(ev) => setEf({ ...ef, from_date: ev.target.value })} />
                      <input type="date" className="h-8 rounded-md border border-border bg-card px-2 text-xs" value={ef.to_date} onChange={(ev) => setEf({ ...ef, to_date: ev.target.value })} />
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => saveEdit(e.id)}>Save</Button>
                      <Button variant="ghost" size="sm" onClick={() => setEditId(null)}>Cancel</Button>
                    </div>
                  </li>
                ) : (
                  <li key={e.id} className="flex items-center justify-between rounded-lg bg-muted px-3 py-2 text-sm">
                    <span>
                      {e.country === "AE" ? "🇦🇪 Dubai" : "🇮🇳 India"} · {e.from_date} → {e.to_date}
                      {e.arr_time && <span className="ml-1">⏱ {e.arr_time}</span>}
                      <span className="ml-2 text-xs text-muted-foreground">({e.source})</span>
                    </span>
                    <span className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => startEdit(e)}>Edit</Button>
                      <Button variant="ghost" size="sm" onClick={() => removeEntry(e.id)}>Delete</Button>
                    </span>
                  </li>
                )
              )}
            </ul>
          )}

          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => quickAdd("AE")}>
              🇦🇪 Mark Dubai
            </Button>
            <Button size="sm" variant="outline" onClick={() => quickAdd("IN")}>
              🇮🇳 Mark India
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

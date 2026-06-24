"use client";

import * as React from "react";
import { Sparkles, Upload } from "lucide-react";
import { api, type TicketSegment } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Row = TicketSegment & { _include: boolean; _source: string };

const inputCls =
  "h-8 rounded-md border border-border bg-card px-2 text-xs outline-none focus:ring-2 focus:ring-primary/30";

export function TicketUploader({
  personId,
  onCommitted,
}: {
  personId: number;
  onCommitted: () => void;
}) {
  const [files, setFiles] = React.useState<File[]>([]);
  const [rows, setRows] = React.useState<Row[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [msg, setMsg] = React.useState<string | null>(null);

  function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const chosen = Array.from(e.target.files ?? []).slice(0, 20);
    setFiles(chosen);
    setMsg(chosen.length === 20 ? "Max 20 tickets per batch." : null);
  }

  async function analyze() {
    if (!files.length) return;
    setBusy(true);
    setMsg("Analysing tickets with AI…");
    try {
      const res = await api.analyzeTickets(personId, files);
      const next: Row[] = [];
      for (const r of res.results) {
        if (r.error) {
          setMsg(`${r.filename}: ${r.error}`);
          continue;
        }
        for (const s of r.segments) {
          next.push({ ...s, _include: true, _source: r.filename });
        }
      }
      setRows(next);
      setMsg(next.length ? `Found ${next.length} flight segment(s). Review and commit.` : "No flights detected.");
    } catch (e: any) {
      setMsg(`Error: ${e.message ?? e}`);
    } finally {
      setBusy(false);
    }
  }

  function patch(i: number, p: Partial<Row>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...p } : r)));
  }

  async function commit() {
    const selected = rows.filter((r) => r._include && r.date);
    if (!selected.length) {
      setMsg("Nothing to commit — each row needs a date and a tick.");
      return;
    }
    setBusy(true);
    try {
      const { created } = await api.commitTickets(personId, selected);
      setMsg(`Added ${created} day-entries to the calendar.`);
      setRows([]);
      setFiles([]);
      onCommitted();
    } catch (e: any) {
      setMsg(`Error: ${e.message ?? e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Sparkles className="mr-1 inline h-3.5 w-3.5" /> Upload Tickets (AI) — up to 20
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Upload boarding passes / flight tickets. AI reads each flight (date + countries);
          a flight day counts for <b>both</b> countries (travel day). Review before saving.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-sm hover:bg-muted">
            <Upload className="h-4 w-4" />
            {files.length ? `${files.length} file(s)` : "Choose images"}
            <input type="file" accept="image/*" multiple className="hidden" onChange={pick} />
          </label>
          <Button size="sm" onClick={analyze} disabled={busy || !files.length}>
            {busy ? "Working…" : "Analyse with AI"}
          </Button>
        </div>

        {rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-muted-foreground">
                <tr className="text-left">
                  <th className="p-1">✓</th>
                  <th className="p-1">Date</th>
                  <th className="p-1">Arr time</th>
                  <th className="p-1">From</th>
                  <th className="p-1">To</th>
                  <th className="p-1">Flight</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="p-1">
                      <input
                        type="checkbox"
                        checked={r._include}
                        onChange={(e) => patch(i, { _include: e.target.checked })}
                      />
                    </td>
                    <td className="p-1">
                      <input
                        type="date"
                        className={inputCls}
                        value={r.date ?? ""}
                        onChange={(e) => patch(i, { date: e.target.value || null })}
                      />
                      {!r.date && <span className="ml-1 text-amber-600">year?</span>}
                    </td>
                    <td className="p-1">
                      <input
                        type="time"
                        className={inputCls}
                        value={r.arr_time ?? ""}
                        onChange={(e) => patch(i, { arr_time: e.target.value || null })}
                        title="Arrival time — bump the date if immigration is next day"
                      />
                    </td>
                    <td className="p-1">
                      <select
                        className={inputCls}
                        value={r.from_country}
                        onChange={(e) => patch(i, { from_country: e.target.value as any })}
                      >
                        <option value="IN">🇮🇳 IN</option>
                        <option value="AE">🇦🇪 AE</option>
                        <option value="OTHER">Other</option>
                      </select>
                      <div className="text-[10px] text-muted-foreground">{r.from_airport}</div>
                    </td>
                    <td className="p-1">
                      <select
                        className={inputCls}
                        value={r.to_country}
                        onChange={(e) => patch(i, { to_country: e.target.value as any })}
                      >
                        <option value="IN">🇮🇳 IN</option>
                        <option value="AE">🇦🇪 AE</option>
                        <option value="OTHER">Other</option>
                      </select>
                      <div className="text-[10px] text-muted-foreground">{r.to_airport}</div>
                    </td>
                    <td className="p-1 text-muted-foreground">{r.flight_no}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Button size="sm" className="mt-3" onClick={commit} disabled={busy}>
              Commit to calendar
            </Button>
          </div>
        )}

        {msg && <p className="text-sm text-muted-foreground">{msg}</p>}
      </CardContent>
    </Card>
  );
}

"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, Plane, Shuffle } from "lucide-react";
import { useProfile } from "@/components/profile-context";
import { api, type Counter, type Summary } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const FLAG: Record<string, string> = { AE: "🇦🇪", IN: "🇮🇳" };

function warnClasses(level: Counter["warnLevel"]) {
  switch (level) {
    case "red":
      return { bar: "bg-red-500", text: "text-red-600", ring: "border-red-200 bg-red-50" };
    case "amber":
      return { bar: "bg-amber-500", text: "text-amber-600", ring: "border-amber-200 bg-amber-50" };
    case "reached":
      return { bar: "bg-emerald-500", text: "text-emerald-600", ring: "border-emerald-200 bg-emerald-50" };
    default:
      return { bar: "bg-primary", text: "text-foreground", ring: "border-border bg-card" };
  }
}

function TargetCard({ c }: { c: Counter }) {
  const cls = warnClasses(c.warnLevel);
  const pct = c.threshold > 0 ? (c.count / c.threshold) * 100 : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {FLAG[c.country]} {c.label} <span className="text-[10px]">(target)</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-end gap-1">
          <span className="text-3xl font-bold tabular-nums">{c.count}</span>
          <span className="pb-1 text-sm text-muted-foreground">/ {c.threshold}</span>
        </div>
        <Progress value={pct} barClassName={cls.bar} />
        <p className="text-sm">
          Pending: <span className={cn("font-semibold", cls.text)}>{c.pending}</span> days left
          {c.warnLevel === "reached" && " — target achieved 🎉"}
        </p>
      </CardContent>
    </Card>
  );
}

function LimitCard({ c }: { c: Counter }) {
  const cls = warnClasses(c.warnLevel);
  const pct = c.threshold > 0 ? (c.count / c.threshold) * 100 : 0;
  return (
    <Card className={c.warnLevel === "red" ? "border-red-300" : undefined}>
      <CardHeader>
        <CardTitle>
          {FLAG[c.country]} {c.label} <span className="text-[10px]">(limit to watch)</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-end gap-1">
          <span className={cn("text-3xl font-bold tabular-nums", cls.text)}>{c.count}</span>
          <span className="pb-1 text-sm text-muted-foreground">/ {c.threshold}</span>
        </div>
        <Progress value={pct} barClassName={cls.bar} />
        <p className="text-sm">
          {c.warnLevel === "red" ? (
            <span className="font-semibold text-red-600">Limit exceeded!</span>
          ) : (
            <>
              <span className={cn("font-semibold", cls.text)}>{c.remainingBeforeLimit}</span> more
              days allowed in India
            </>
          )}
        </p>
      </CardContent>
    </Card>
  );
}

function AllowanceCard({ c }: { c: Counter }) {
  const negative = (c.allowance ?? 0) < 0;
  return (
    <Card className={negative ? "border-red-300" : "border-emerald-200"}>
      <CardHeader>
        <CardTitle>
          <Shuffle className="mr-1 inline h-3.5 w-3.5" /> Allowance
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex items-end gap-1">
          <span
            className={cn(
              "text-3xl font-bold tabular-nums",
              negative ? "text-red-600" : "text-emerald-600"
            )}
          >
            {c.allowance}
          </span>
          <span className="pb-1 text-sm text-muted-foreground">days</span>
        </div>
        <p className="text-sm text-muted-foreground">
          {negative ? (
            <>You're this many days behind — the {c.label.replace(" Days", "")} target ({c.threshold})
            can't be reached in this window without adding more Dubai days.</>
          ) : (
            <>You can still spend this many days <b>outside</b> Dubai and still reach {c.threshold}.</>
          )}
        </p>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { current } = useProfile();
  const [summary, setSummary] = React.useState<Summary | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!current) return;
    setSummary(null);
    setErr(null);
    api.summary(current.id).then(setSummary).catch((e) => setErr(String(e.message ?? e)));
  }, [current]);

  if (!current) return null;
  if (err) return <p className="text-sm text-red-600">{err}</p>;
  if (!summary) return <p className="text-sm text-muted-foreground">Loading dashboard…</p>;

  const target = summary.counters.find((c) => c.mode === "target_to_reach");
  const limit = summary.counters.find((c) => c.mode === "limit_to_watch");

  return (
    <div className="space-y-6">
      {summary.incomplete && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <b>{summary.unknownDays} unknown days</b> have no data. Counts may be incomplete —{" "}
            <Link href="/calendar" className="font-semibold underline">
              fill them in the calendar
            </Link>
            .
          </span>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {target && <TargetCard c={target} />}
        {limit && <LimitCard c={limit} />}
        {target && <AllowanceCard c={target} />}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>
              <Plane className="mr-1 inline h-3.5 w-3.5" /> Travel Days
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-2xl font-bold tabular-nums">{summary.travelDays}</span>
            <p className="text-xs text-muted-foreground">
              Days credited to both countries (🇮🇳🇦🇪).
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Unknown Days</CardTitle>
          </CardHeader>
          <CardContent>
            <span
              className={cn(
                "text-2xl font-bold tabular-nums",
                summary.unknownDays > 0 ? "text-amber-600" : "text-foreground"
              )}
            >
              {summary.unknownDays}
            </span>
            <p className="text-xs text-muted-foreground">
              Past days with no data (`?`). Filling them makes counts accurate.
            </p>
          </CardContent>
        </Card>
      </div>

      <p className="text-xs text-muted-foreground">
        As of {summary.asOf}. Windows: Dubai = calendar year, India = financial year.
      </p>
    </div>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarCheck, CalendarDays, Home, Plane, PlusCircle, Settings } from "lucide-react";
import { useProfile } from "@/components/profile-context";
import { API_BASE } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/entry", label: "Add Entry", icon: PlusCircle },
  { href: "/commitments", label: "Commitments", icon: CalendarCheck },
  { href: "/trips", label: "Trips", icon: Plane },
  { href: "/settings", label: "Settings", icon: Settings },
];

function ProfileSwitcher() {
  const { persons, current, setCurrentId } = useProfile();
  return (
    <div className="flex gap-1 rounded-lg bg-muted p-1">
      {persons.map((p) => (
        <button
          key={p.id}
          onClick={() => setCurrentId(p.id)}
          className={cn(
            "rounded-md px-4 py-1.5 text-sm font-semibold transition-colors",
            current?.id === p.id
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {p.code}
        </button>
      ))}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { current, loading, error } = useProfile();

  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4">
      <header className="flex flex-wrap items-center justify-between gap-3 py-5">
        <div>
          <h1 className="text-lg font-bold tracking-tight">NRI Residency Tracker</h1>
          <p className="text-xs text-muted-foreground">
            {current ? `Profile: ${current.code}` : "Loading profile…"}
          </p>
        </div>
        <ProfileSwitcher />
      </header>

      <nav className="mb-6 flex flex-wrap gap-1 border-b border-border pb-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <main className="flex-1 pb-16">
        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Couldn't connect to the backend: {error}. Check that the API is
            reachable{API_BASE ? ` (${API_BASE})` : " — NEXT_PUBLIC_API_BASE is not set"}.
          </div>
        ) : loading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : (
          children
        )}
      </main>
    </div>
  );
}

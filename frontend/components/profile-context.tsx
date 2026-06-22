"use client";

import * as React from "react";
import { api, type Person } from "@/lib/api";

type Ctx = {
  persons: Person[];
  current: Person | null;
  setCurrentId: (id: number) => void;
  loading: boolean;
  error: string | null;
};

const ProfileContext = React.createContext<Ctx | null>(null);

const STORAGE_KEY = "nri.currentPersonId";

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const [persons, setPersons] = React.useState<Person[]>([]);
  const [currentId, setCurrentIdState] = React.useState<number | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .persons()
      .then((p) => {
        setPersons(p);
        const saved = Number(localStorage.getItem(STORAGE_KEY));
        const initial = p.find((x) => x.id === saved)?.id ?? p[0]?.id ?? null;
        setCurrentIdState(initial);
      })
      .catch((e) => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }, []);

  const setCurrentId = React.useCallback((id: number) => {
    setCurrentIdState(id);
    localStorage.setItem(STORAGE_KEY, String(id));
  }, []);

  const current = persons.find((p) => p.id === currentId) ?? null;

  return (
    <ProfileContext.Provider value={{ persons, current, setCurrentId, loading, error }}>
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  const ctx = React.useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used within ProfileProvider");
  return ctx;
}

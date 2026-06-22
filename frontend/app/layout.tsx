import type { Metadata } from "next";
import "./globals.css";
import { ProfileProvider } from "@/components/profile-context";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "NRI Residency Tracker",
  description: "Track India / Dubai days for NRI status across NKA, KKA, HKA",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ProfileProvider>
          <AppShell>{children}</AppShell>
        </ProfileProvider>
      </body>
    </html>
  );
}

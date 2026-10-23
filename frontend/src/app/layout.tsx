import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "PR Chronicler — AI-Powered Open-Source Contribution Explorer & Outreach",
  description: "Explore GitHub contributions, analyze code changes with Gemini, and connect with open-source contributors.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="h-full bg-slate-50 text-slate-900 selection:bg-indigo-500 selection:text-white">
        <Suspense fallback={null}>
          <AppShell>{children}</AppShell>
        </Suspense>
      </body>
    </html>
  );
}

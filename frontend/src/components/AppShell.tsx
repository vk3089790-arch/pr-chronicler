"use client";

import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export const RefreshContext = React.createContext<{
  refreshKey: number;
  triggerRefresh: () => void;
  isRefreshing: boolean;
  setIsRefreshing: (val: boolean) => void;
}>({
  refreshKey: 0,
  triggerRefresh: () => {},
  isRefreshing: false,
  setIsRefreshing: () => {},
});

export function AppShell({ children }: { children: React.ReactNode }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const triggerRefresh = () => {
    setIsRefreshing(true);
    setRefreshKey((prev) => prev + 1);
    setTimeout(() => setIsRefreshing(false), 600);
  };

  return (
    <RefreshContext.Provider
      value={{ refreshKey, triggerRefresh, isRefreshing, setIsRefreshing }}
    >
      <div className="flex h-screen w-full bg-slate-50 text-slate-900 font-sans overflow-hidden">
        {/* Dark Navy / Slate Persistent Sidebar */}
        <React.Suspense fallback={<div className="w-64 bg-slate-900 min-h-screen shrink-0" />}>
          <Sidebar />
        </React.Suspense>

        {/* Main Content Workspace */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <React.Suspense fallback={<div className="h-16 bg-white border-b border-slate-200" />}>
            <Header onRefresh={triggerRefresh} isRefreshing={isRefreshing} />
          </React.Suspense>
          <main className="flex-1 overflow-y-auto p-6 md:p-8">
            <div className="max-w-7xl mx-auto space-y-6">{children}</div>
          </main>
        </div>
      </div>
    </RefreshContext.Provider>
  );
}

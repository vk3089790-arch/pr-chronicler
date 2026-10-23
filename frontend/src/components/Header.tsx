"use client";

import React, { useEffect, useState, useCallback } from "react";
import { usePathname } from "next/navigation";
import { RefreshCw, AlertCircle, ArrowUpRight } from "lucide-react";
import { api } from "@/lib/api";

const TITLES: Record<string, { title: string; subtitle: string }> = {
  "/": {
    title: "Overview Dashboard",
    subtitle: "Real-time metrics, system health, and merged PR reflection activity",
  },
  "/pull-requests": {
    title: "Pull Requests",
    subtitle: "Search, filter, and inspect processed GitHub pull requests and diff reflections",
  },
  "/learnings": {
    title: "Key Takeaways & Learnings",
    subtitle: "Evidence-grounded engineering takeaways extracted by Gemini reflection chains",
  },
  "/webhook-events": {
    title: "Webhook Audit Log",
    subtitle: "Inbound GitHub webhook deliveries, signature checks, and idempotency states",
  },
  "/email-deliveries": {
    title: "Email Deliveries",
    subtitle: "Persisted SMTP reflection dispatch history with recipient privacy protection",
  },
  "/system-health": {
    title: "System Health & Integrations",
    subtitle: "Subsystem readiness for FastAPI, SQLite WAL, Gemini, GitHub API, and SMTP",
  },
  "/settings": {
    title: "Application Settings",
    subtitle: "Safe configuration inspection, secret policies, and operational guidance",
  },
};

interface HeaderProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function Header({ onRefresh, isRefreshing = false }: HeaderProps) {
  const pathname = usePathname();
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(false);

  const checkHealth = useCallback(async () => {
    setChecking(true);
    try {
      const data = await api.getSystemHealth();
      setBackendOnline(data.status === "healthy");
    } catch {
      setBackendOnline(false);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 20000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  const current = TITLES[pathname] || {
    title: "Dashboard",
    subtitle: "PR Chronicler Management Console",
  };

  const handleRefreshClick = () => {
    checkHealth();
    if (onRefresh) {
      onRefresh();
    }
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-8 flex items-center justify-between shrink-0 sticky top-0 z-10 shadow-2xs">
      <div>
        <h2 className="text-base font-semibold text-slate-900 tracking-tight">{current.title}</h2>
        <p className="text-xs text-slate-500 hidden sm:block">{current.subtitle}</p>
      </div>

      <div className="flex items-center gap-3">
        {/* Backend live status indicator */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
            backendOnline === true
              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
              : backendOnline === false
              ? "bg-rose-50 text-rose-700 border-rose-200"
              : "bg-slate-50 text-slate-600 border-slate-200"
          }`}
          title={
            backendOnline === true
              ? "Backend API is responding at http://localhost:8000"
              : "Backend API is unreachable"
          }
        >
          {backendOnline === true ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Backend Connected</span>
            </>
          ) : backendOnline === false ? (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
              <span>Backend Offline</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-slate-400" />
              <span>Checking...</span>
            </>
          )}
        </div>

        {/* Refresh button */}
        <button
          onClick={handleRefreshClick}
          disabled={isRefreshing || checking}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors cursor-pointer disabled:opacity-60"
          title="Refresh current page data"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing || checking ? "animate-spin text-indigo-600" : ""}`} />
          <span>Refresh</span>
        </button>

        {/* API Docs Button */}
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="hidden md:flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50/80 hover:bg-indigo-100/80 border border-indigo-200/80 rounded-lg transition-colors"
        >
          <span>Swagger UI</span>
          <ArrowUpRight className="w-3 h-3" />
        </a>
      </div>
    </header>
  );
}

"use client";

import React, { useEffect, useState, useContext, useCallback } from "react";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  Database,
  Cpu,
  Mail,
  ShieldCheck,
  GitBranch,
  Server,
  RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";
import { SystemHealthData } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { RefreshContext } from "@/components/AppShell";

export default function SystemHealthPage() {
  const { refreshKey, setIsRefreshing } = useContext(RefreshContext);
  const [health, setHealth] = useState<SystemHealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getSystemHealth();
      setHealth(data);
      setLastChecked(new Date());
    } catch (err) {
      console.error("Failed to fetch system health:", err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [setIsRefreshing]);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth, refreshKey]);

  if (loading && !health) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-28 bg-white rounded-xl border border-slate-200 animate-pulse" />
        ))}
      </div>
    );
  }

  if (!health) {
    return (
      <EmptyState
        title="Health Check Failed"
        description="Could not connect to FastAPI health endpoint at http://localhost:8000/api/system/health"
        icon={AlertTriangle}
        actionText="Retry Health Diagnostic"
        onAction={fetchHealth}
      />
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Health Status Banner */}
      <div
        className={`p-5 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
          health.status === "healthy"
            ? "bg-emerald-50/60 border-emerald-200 text-emerald-900"
            : "bg-amber-50/60 border-amber-200 text-amber-900"
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`p-2 rounded-lg ${
              health.status === "healthy" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
            }`}
          >
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-semibold text-sm">
              System Status: {health.status === "healthy" ? "All Subsystems Operational" : "Degraded Readiness"}
            </h3>
            <p className="text-xs text-slate-600 mt-0.5">
              Service: <span className="font-mono">{health.service}</span> v{health.version} • SQLite WAL
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-500 font-mono">
          {lastChecked && (
            <span>Last checked: {lastChecked.toLocaleTimeString()}</span>
          )}
          <button
            onClick={fetchHealth}
            className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 flex items-center gap-1.5 transition-colors cursor-pointer font-sans"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Run Diagnostic
          </button>
        </div>
      </div>

      {/* Subsystems Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* 1. FastAPI Application */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-indigo-600" />
              <h4 className="font-semibold text-xs uppercase tracking-wider text-slate-600">
                FastAPI Server
              </h4>
            </div>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
              <CheckCircle2 className="w-3.5 h-3.5" /> Running
            </span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Service Title</span>
              <span className="font-semibold text-slate-800">{health.service}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">API Documentation</span>
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-600 hover:underline font-mono"
              >
                /docs (Swagger)
              </a>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Health Endpoint</span>
              <span className="font-mono text-slate-800">/health</span>
            </div>
          </div>
        </div>

        {/* 2. SQLite Database */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-emerald-600" />
              <h4 className="font-semibold text-xs uppercase tracking-wider text-slate-600">
                SQLite Persistence
              </h4>
            </div>
            <span
              className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
                health.database.connected
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-rose-700 bg-rose-50 border-rose-200"
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              {health.database.connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Database Path</span>
              <span className="font-mono text-slate-800">{health.database.path}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Journal Mode</span>
              <span className="font-mono font-semibold text-emerald-700">
                {health.database.wal_mode ? "WAL Mode (Concurrent)" : "Standard"}
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Total Tracked Events</span>
              <span className="font-semibold text-slate-800">{health.database.total_deliveries}</span>
            </div>
          </div>
        </div>

        {/* 3. Google Gemini Model */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-purple-600" />
              <h4 className="font-semibold text-xs uppercase tracking-wider text-slate-600">
                Google Gemini LLM
              </h4>
            </div>
            <span
              className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
                health.gemini.configured
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-rose-700 bg-rose-50 border-rose-200"
              }`}
            >
              {health.gemini.configured ? "Key Configured" : "Missing Key"}
            </span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Configured Model</span>
              <span className="font-mono text-slate-800">{health.gemini.model}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Effective Model</span>
              <span className="font-mono font-semibold text-indigo-700">
                {health.gemini.effective_model}
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Sampling Temperature</span>
              <span className="font-mono text-slate-800">{health.gemini.temperature}</span>
            </div>
          </div>
        </div>

        {/* 4. GitHub API Integration */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitBranch className="w-5 h-5 text-slate-800" />
              <h4 className="font-semibold text-xs uppercase tracking-wider text-slate-600">
                GitHub REST API
              </h4>
            </div>
            <span
              className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
                health.github.token_configured
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-amber-700 bg-amber-50 border-amber-200"
              }`}
            >
              {health.github.token_configured ? "Token Present" : "Unauthenticated"}
            </span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Rate Limit Tier</span>
              <span className="font-semibold text-slate-800">
                {health.github.token_configured ? "5,000 requests/hr" : "60 requests/hr"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">PR Context Hydration</span>
              <span className="text-emerald-700 font-semibold">Diffs & Issues Enabled</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Token Privacy</span>
              <span className="text-slate-600 font-mono">Redacted (Never displayed)</span>
            </div>
          </div>
        </div>

        {/* 5. SMTP Email Dispatcher */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-blue-600" />
              <h4 className="font-semibold text-xs uppercase tracking-wider text-slate-600">
                SMTP Dispatcher
              </h4>
            </div>
            <span
              className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
                health.smtp.configured
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-rose-700 bg-rose-50 border-rose-200"
              }`}
            >
              {health.smtp.configured ? "Ready" : "Incomplete"}
            </span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Host & Port</span>
              <span className="font-mono text-slate-800">
                {health.smtp.host}:{health.smtp.port}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">STARTTLS Security</span>
              <span className="font-semibold text-emerald-700">
                {health.smtp.use_tls ? "Enabled (Port 587)" : "Disabled"}
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Recipient Configured</span>
              <span className="font-semibold text-slate-800">
                {health.smtp.recipient_configured ? "Yes" : "No"}
              </span>
            </div>
          </div>
        </div>

        {/* 6. Webhook HMAC Security */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-600" />
              <h4 className="font-semibold text-xs uppercase tracking-wider text-slate-600">
                Webhook Security
              </h4>
            </div>
            <span
              className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
                health.webhook_security.secret_enforced
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-amber-700 bg-amber-50 border-amber-200"
              }`}
            >
              {health.webhook_security.secret_enforced ? "Enforced" : "Optional"}
            </span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Signature Algorithm</span>
              <span className="font-mono font-semibold text-slate-800">HMAC-SHA256</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Expected Header</span>
              <span className="font-mono text-slate-800">X-Hub-Signature-256</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Secret Privacy</span>
              <span className="text-slate-600 font-mono">Redacted (Never displayed)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

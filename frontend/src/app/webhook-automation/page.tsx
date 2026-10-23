"use client";

import React, { useEffect, useState, useContext, useCallback } from "react";
import Link from "next/link";
import {
  GitPullRequest,
  CheckCircle2,
  XCircle,
  BookOpen,
  Mail,
  Activity,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Webhook,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { DashboardSummary } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { Badge } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { CardSkeleton } from "@/components/LoadingSkeleton";
import { RefreshContext } from "@/components/AppShell";

export default function WebhookAutomationPage() {
  const { refreshKey, setIsRefreshing } = useContext(RefreshContext);
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const summary = await api.getDashboardSummary();
      setData(summary);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to load metrics: ${err.message}`);
      } else {
        setError("Unable to connect to PR Chronicler backend at http://localhost:8000");
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [setIsRefreshing]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard, refreshKey]);

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <EmptyState
        title="Backend Offline or Unreachable"
        description={error}
        icon={AlertTriangle}
        actionText="Retry Connection"
        onAction={fetchDashboard}
      />
    );
  }

  const summary = data!;
  const completedPercent =
    summary.total_deliveries > 0
      ? Math.round((summary.completed_jobs / summary.total_deliveries) * 100)
      : 0;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 to-indigo-950 rounded-xl p-6 text-white border border-slate-800 shadow-md">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
                <Webhook className="w-5 h-5" />
              </span>
              <h2 className="text-xl font-bold tracking-tight">Webhook Automation Engine</h2>
            </div>
            <p className="text-sm text-slate-300 max-w-2xl">
              Real-time monitoring of automated merged-PR webhook deliveries. Verified with HMAC-SHA256,
              hydrated with full diffs, analyzed by Gemini, and dispatched to your team&apos;s email.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/webhook-events"
              className="px-3.5 py-2 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors border border-slate-700"
            >
              Raw Events
            </Link>
            <Link
              href="/email-deliveries"
              className="px-3.5 py-2 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors shadow-xs"
            >
              Email Deliveries
            </Link>
          </div>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total PRs"
          value={summary.total_prs}
          subtitle={`${summary.total_deliveries} total event deliveries`}
          icon={GitPullRequest}
          variant="default"
        />
        <StatCard
          title="Completed Reflections"
          value={summary.completed_jobs}
          subtitle={`${completedPercent}% completion rate`}
          icon={CheckCircle2}
          variant="success"
        />
        <StatCard
          title="Failed Jobs"
          value={summary.failed_jobs}
          subtitle={`${summary.ignored_jobs} events safely ignored`}
          icon={XCircle}
          variant="danger"
        />
        <StatCard
          title="Extracted Learnings"
          value={summary.total_learnings}
          subtitle="Grounded Gemini takeaways"
          icon={BookOpen}
          variant="info"
        />
        <StatCard
          title="Emails Dispatched"
          value={summary.total_emails_sent}
          subtitle="SMTP reports delivered"
          icon={Mail}
          variant="warning"
        />
      </div>

      {/* System Readiness & Integrations Pill Grid */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-semibold text-slate-900">Subsystem Readiness</h3>
          </div>
          <Link
            href="/system-health"
            className="text-xs font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
          >
            Full Diagnostics <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-slate-500">FastAPI Backend</span>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-xs font-semibold text-slate-800">Online</span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-slate-500">Database</span>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-xs font-semibold text-slate-800">SQLite WAL</span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-slate-500">Gemini LLM</span>
            <div className="mt-1 flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  summary.system_status.gemini_configured ? "bg-emerald-500" : "bg-rose-500"
                }`}
              />
              <span className="text-xs font-semibold text-slate-800 font-mono text-[11px]">
                {summary.system_status.gemini_model}
              </span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-slate-500">GitHub API</span>
            <div className="mt-1 flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  summary.system_status.github_token_configured ? "bg-emerald-500" : "bg-amber-500"
                }`}
              />
              <span className="text-xs font-semibold text-slate-800">
                {summary.system_status.github_token_configured ? "Authenticated" : "Rate-limited"}
              </span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-slate-500">SMTP Dispatch</span>
            <div className="mt-1 flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  summary.system_status.smtp_configured ? "bg-emerald-500" : "bg-rose-500"
                }`}
              />
              <span className="text-xs font-semibold text-slate-800">
                {summary.system_status.smtp_configured ? "Configured" : "Disabled"}
              </span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-slate-500">Webhook HMAC</span>
            <div className="mt-1 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-xs font-semibold text-slate-800">
                {summary.system_status.webhook_secret_enforced ? "Enforced" : "Optional"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Two-Column Section: Recent Activity & Recent Failures */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 spans): Recent Activity */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 shadow-xs flex flex-col">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-500" />
              <h3 className="text-sm font-semibold text-slate-900">Recent Webhook Activity</h3>
            </div>
            <Link
              href="/pull-requests"
              className="text-xs font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
            >
              View all PRs <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="divide-y divide-slate-100 flex-1">
            {summary.recent_activity.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">No activity recorded yet</div>
            ) : (
              summary.recent_activity.map((item) => (
                <div
                  key={item.delivery_id}
                  className="px-6 py-3.5 flex items-center justify-between hover:bg-slate-50/60 transition-colors"
                >
                  <div className="min-w-0 flex-1 pr-4">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-xs text-slate-900 truncate">
                        {item.repo}
                      </span>
                      <span className="text-xs text-indigo-600 font-mono">#{item.pr_number}</span>
                      <Badge status={item.status} size="sm" />
                    </div>
                    <p className="text-xs text-slate-600 truncate mt-0.5">
                      {item.pr_title || `Pull Request #${item.pr_number}`}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <time className="text-[11px] text-slate-400 font-mono">
                      {new Date(item.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </time>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Column (1 span): Recent Errors & Failures */}
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs flex flex-col">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-500" />
              <h3 className="text-sm font-semibold text-slate-900">Recent Processing Errors</h3>
            </div>
            <span className="text-xs text-slate-500 font-mono">
              {summary.recent_errors.length} recorded
            </span>
          </div>

          <div className="p-4 space-y-3 flex-1 overflow-y-auto max-h-[400px]">
            {summary.recent_errors.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-400">
                No recent errors recorded. Pipeline operating smoothly.
              </div>
            ) : (
              summary.recent_errors.map((err) => (
                <div
                  key={err.delivery_id}
                  className="p-3 rounded-lg bg-rose-50/50 border border-rose-100 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-rose-900">
                      {err.repo} #{err.pr_number}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {new Date(err.updated_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="text-rose-700 font-mono text-[11px] line-clamp-3 bg-white/70 p-2 rounded border border-rose-100/80">
                    {err.error_message}
                  </p>
                  <div className="text-[10px] text-slate-500 font-mono truncate">
                    ID: {err.delivery_id}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import React, { useEffect, useState, useContext, useCallback } from "react";
import {
  ShieldCheck,
  Server,
  Cpu,
  Mail,
  Key,
  Info,
} from "lucide-react";
import { api } from "@/lib/api";
import { SettingsData } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { RefreshContext } from "@/components/AppShell";

export default function SettingsPage() {
  const { refreshKey, setIsRefreshing } = useContext(RefreshContext);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (err) {
      console.error("Failed to load settings:", err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [setIsRefreshing]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings, refreshKey]);

  if (loading && !settings) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-36 bg-white rounded-xl border border-slate-200 animate-pulse" />
        ))}
      </div>
    );
  }

  if (!settings) {
    return (
      <EmptyState
        title="Settings Unavailable"
        description="Unable to retrieve configuration from backend /api/settings endpoint."
        actionText="Retry"
        onAction={fetchSettings}
      />
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200 max-w-5xl">
      {/* Security & Secrets Guarantee Banner */}
      <div className="bg-indigo-50/60 border border-indigo-100 rounded-xl p-4 flex items-start gap-3 text-xs text-indigo-900">
        <ShieldCheck className="w-5 h-5 text-indigo-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="font-semibold text-indigo-950">Zero-Secret Exposure Policy</div>
          <p className="text-indigo-800 leading-relaxed">
            All sensitive credentials (Gemini API keys, GitHub tokens, SMTP app passwords, and HMAC secrets)
            are securely confined to the root server environment. The API and UI will never transmit or display raw credentials.
          </p>
        </div>
      </div>

      {/* Configuration Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Environment & Server Card */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <Server className="w-4 h-4 text-slate-700" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
              Runtime Environment
            </h3>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">FastAPI Host & Port</span>
              <span className="font-mono text-slate-800">
                {settings.environment.host}:{settings.environment.port}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Database Storage</span>
              <span className="font-mono text-slate-800">{settings.environment.database_path}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Log File Destination</span>
              <span className="font-mono text-slate-800">{settings.environment.log_file}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Active Logging Level</span>
              <span className="font-mono font-semibold text-indigo-600">{settings.environment.log_level}</span>
            </div>
          </div>
        </div>

        {/* Gemini Engine Card */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <Cpu className="w-4 h-4 text-purple-600" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
              Gemini LLM Pipeline
            </h3>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Model Identifier</span>
              <span className="font-mono font-semibold text-slate-800">{settings.gemini.model}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Chain Sampling Temperature</span>
              <span className="font-mono text-slate-800">{settings.gemini.temperature}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">API Key Status</span>
              <span className="font-medium text-emerald-600">
                {settings.gemini.api_key_configured ? "Configured & Active" : "Missing API Key"}
              </span>
            </div>
          </div>
        </div>

        {/* SMTP Mail Dispatch Card */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <Mail className="w-4 h-4 text-blue-600" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
              SMTP Dispatch Configuration
            </h3>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">SMTP Server & Port</span>
              <span className="font-mono text-slate-800">
                {settings.smtp.host}:{settings.smtp.port} (TLS={String(settings.smtp.use_tls)})
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Sender Address</span>
              <span className="font-mono text-slate-800">{settings.smtp.sender_email_masked}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Recipient Address</span>
              <span className="font-mono text-slate-800">{settings.smtp.recipient_email_masked}</span>
            </div>
          </div>
        </div>

        {/* Webhook Security Card */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <Key className="w-4 h-4 text-emerald-600" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
              Webhook & GitHub Security
            </h3>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">GitHub Token</span>
              <span className="font-medium text-slate-800">
                {settings.github.token_configured ? "Token Active (5k/hr limit)" : "Unauthenticated"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">HMAC-SHA256 Verification</span>
              <span className="font-semibold text-emerald-600">
                {settings.github.webhook_secret_configured ? "Enforced (Secret Active)" : "Optional"}
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Signature Header</span>
              <span className="font-mono text-slate-800">X-Hub-Signature-256</span>
            </div>
          </div>
        </div>
      </div>

      {/* Operational Guidance Section */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
          <Info className="w-5 h-5 text-indigo-600" />
          <h3 className="text-sm font-semibold text-slate-900">
            Operational Guidance & Administration
          </h3>
        </div>

        <div className="space-y-3 text-xs text-slate-600 leading-relaxed">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
            <span className="font-semibold text-slate-800 block">Modifying Configuration</span>
            <p>
              To change credentials or configuration, edit the root <span className="font-mono text-slate-800">.env</span> file directly and restart the FastAPI server. Never commit your <span className="font-mono text-slate-800">.env</span> file to git.
            </p>
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
            <span className="font-semibold text-slate-800 block">In-Process Background Processing Notice</span>
            <p>
              {settings.operational_guidance.background_workers}
            </p>
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
            <span className="font-semibold text-slate-800 block">Simulating Webhooks via CLI</span>
            <p className="font-mono text-[11px] text-slate-700">
              python3 simulate_merge.py --repo pallets/flask --pr 6168
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

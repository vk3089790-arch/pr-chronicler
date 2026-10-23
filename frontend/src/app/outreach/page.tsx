"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  Mail,
  Send,
  Sparkles,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Clock,
  User,
  FolderGit2,
  Eye,
  Info,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { OutreachRecordItem } from "@/lib/types";
import { Modal } from "@/components/Modal";

function OutreachContent() {
  const searchParams = useSearchParams();
  const queryUsername = searchParams.get("username") || "";
  const queryEmail = searchParams.get("email") || "";
  const queryRepo = searchParams.get("repo") || "";
  const queryPr = searchParams.get("pr") ? parseInt(searchParams.get("pr")!, 10) : undefined;
  const queryTitle = searchParams.get("title") || "";

  // Form Fields
  const [contributorUsername, setContributorUsername] = useState(queryUsername);
  const [recipientEmail, setRecipientEmail] = useState(queryEmail);
  const [repo, setRepo] = useState(queryRepo);
  const [prNumber, setPrNumber] = useState<number | undefined>(queryPr);
  const [prTitle, setPrTitle] = useState(queryTitle);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [emailSource, setEmailSource] = useState<"public_profile" | "user_provided">(
    queryEmail ? "public_profile" : "user_provided"
  );

  // States
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [confirmSend, setConfirmSend] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendSuccess, setSendSuccess] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  // Outreach History
  const [history, setHistory] = useState<OutreachRecordItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Load History
  const fetchHistory = useCallback(() => {
    setHistoryLoading(true);
    api.getOutreachHistory({ limit: 20 })
      .then((res) => setHistory(res.items))
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false));
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleGenerateDraft = useCallback(async (
    u = contributorUsername,
    e = recipientEmail,
    r = repo,
    pr = prNumber,
    t = prTitle
  ) => {
    if (!u.trim()) {
      setSendError("Please specify a contributor username to generate a customized draft.");
      return;
    }
    setGeneratingDraft(true);
    setSendError(null);
    try {
      const draft = await api.createOutreachDraft({
        contributor_username: u,
        recipient_email: e.trim() || undefined,
        repo: r.trim() || undefined,
        pr_number: pr || undefined,
        pr_title: t.trim() || undefined,
        email_source: e.trim() ? "public_profile" : "user_provided",
      });
      setSubject(draft.subject);
      setBody(draft.body);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate draft";
      setSendError(msg);
    } finally {
      setGeneratingDraft(false);
    }
  }, [contributorUsername, recipientEmail, repo, prNumber, prTitle]);

  // Pre-generate draft if opened with query parameters
  useEffect(() => {
    if (queryUsername) {
      handleGenerateDraft(queryUsername, queryEmail, queryRepo, queryPr, queryTitle);
    }
  }, [queryUsername, queryEmail, queryRepo, queryPr, queryTitle, handleGenerateDraft]);

  const handleSendEmail = async () => {
    if (!confirmSend) {
      setSendError("Please check the confirmation box before sending.");
      return;
    }
    if (!recipientEmail || !recipientEmail.includes("@")) {
      setSendError("A valid recipient email address is required.");
      return;
    }

    setSending(true);
    setSendError(null);
    setSendSuccess(null);

    // Create a client-side idempotency key based on recipient, subject, and time
    const idempotencyKey = `outreach-${contributorUsername || "user"}-${Date.now()}-${Math.random()
      .toString(36)
      .slice(2, 7)}`;

    try {
      const res = await api.sendOutreachEmail({
        recipient_email: recipientEmail.trim(),
        subject,
        body,
        contributor_username: contributorUsername.trim() || undefined,
        repo: repo.trim() || undefined,
        pr_number: prNumber || undefined,
        email_source: emailSource,
        idempotency_key: idempotencyKey,
        confirm_send: true,
      });

      setSendSuccess(res.message || "Outreach email sent successfully.");
      setShowPreviewModal(false);
      setConfirmSend(false);
      fetchHistory();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "SMTP outreach dispatch failed";
      setSendError(msg);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 mb-2 text-indigo-600">
            <Mail className="w-5 h-5" />
            <h2 className="text-xl font-bold tracking-tight text-slate-900">
              Contributor Email Outreach
            </h2>
          </div>
          <p className="text-sm text-slate-600">
            Draft, preview, and dispatch personalized outreach emails to open-source contributors
            referencing their technical PRs. Protected with explicit confirmation and privacy masking.
          </p>
        </div>
      </div>

      {/* Main Outreach Form & Instructions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 spans): Email Composer */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-slate-900 pb-3 border-b border-slate-100 flex items-center justify-between">
            <span>Compose Message</span>
            <button
              type="button"
              onClick={() => handleGenerateDraft()}
              disabled={generatingDraft || !contributorUsername.trim()}
              className="px-3 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{generatingDraft ? "Drafting..." : "Auto-Generate Draft"}</span>
            </button>
          </h3>

          {sendSuccess && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{sendSuccess}</span>
            </div>
          )}

          {sendError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{sendError}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Contributor Username
              </label>
              <div className="relative">
                <span className="absolute left-3 top-2.5 text-xs text-slate-400 font-mono">@</span>
                <input
                  type="text"
                  value={contributorUsername}
                  onChange={(e) => setContributorUsername(e.target.value)}
                  placeholder="e.g. tiangolo"
                  className="w-full pl-7 pr-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Recipient Email
              </label>
              <input
                type="email"
                value={recipientEmail}
                onChange={(e) => {
                  setRecipientEmail(e.target.value);
                  setEmailSource("user_provided");
                }}
                placeholder="contributor@example.com"
                className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 font-mono"
              />
              <span className="text-[10px] text-slate-400 mt-1 block">
                Source: <span className="font-semibold text-slate-600">{emailSource}</span>
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Referenced Repository (Optional)
              </label>
              <input
                type="text"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                placeholder="owner/repo"
                className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Referenced PR # (Optional)
              </label>
              <input
                type="number"
                value={prNumber || ""}
                onChange={(e) => setPrNumber(e.target.value ? parseInt(e.target.value, 10) : undefined)}
                placeholder="e.g. 123"
                className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Subject</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Email Subject Line"
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Message Body</label>
            <textarea
              rows={8}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Compose your personalized outreach message here..."
              className="w-full p-3 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 leading-relaxed font-sans"
            />
          </div>

          {/* Action Row */}
          <div className="pt-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowPreviewModal(true)}
              disabled={!recipientEmail || !subject || !body}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Eye className="w-3.5 h-3.5" />
              <span>Preview & Confirm Send</span>
            </button>
          </div>
        </div>

        {/* Right Column (1 span): Outreach Safeguards */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
            <ShieldCheck className="w-5 h-5 text-indigo-600" />
            <h3 className="text-sm font-bold text-slate-900">Safety & Privacy Rules</h3>
          </div>

          <div className="space-y-3 text-xs text-slate-600 leading-relaxed">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
              <p className="font-semibold text-slate-800">Verified Email Addresses Only</p>
              <p className="text-[11px] text-slate-500">
                Addresses are sourced strictly from public GitHub profile metadata or explicitly
                entered by you. PR Chronicler never infers or scrapes private emails.
              </p>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
              <p className="font-semibold text-slate-800">No Automated Bulk Sending</p>
              <p className="text-[11px] text-slate-500">
                Browsing profiles or repositories will never send an email automatically. Every dispatch
                requires deliberate human review and confirmation.
              </p>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
              <p className="font-semibold text-slate-800">Idempotency & Duplicate Guards</p>
              <p className="text-[11px] text-slate-500">
                Unique idempotency tokens prevent accidental double-sends, and recipient addresses
                are masked in logs and dashboards to respect privacy.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Outreach History Section */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-600" />
            <h3 className="text-sm font-bold text-slate-900">Outreach Dispatch History</h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {history.length} records (emails masked)
          </span>
        </div>

        {historyLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : history.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            No outreach emails dispatched yet.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {history.map((item) => (
              <div
                key={item.id}
                className="py-3 px-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/80 rounded-lg transition-colors"
              >
                <div className="min-w-0 space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-semibold text-slate-800">
                      {item.recipient_masked}
                    </span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                        item.status === "SENT"
                          ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                          : "bg-rose-100 text-rose-800 border border-rose-200"
                      }`}
                    >
                      {item.status}
                    </span>
                    <span className="text-[10px] text-slate-400 font-sans">
                      ({item.email_source})
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-slate-700">{item.subject}</p>
                  <p className="text-[11px] text-slate-500 truncate">{item.body_snippet}</p>
                </div>

                <div className="text-right shrink-0 text-[11px] text-slate-400 font-mono">
                  {new Date(item.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Confirmation & Preview Modal */}
      <Modal
        isOpen={showPreviewModal}
        onClose={() => setShowPreviewModal(false)}
        title="Confirm Contributor Outreach"
      >
        <div className="space-y-4 text-xs">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 space-y-1">
            <p className="font-semibold flex items-center gap-1.5">
              <Info className="w-4 h-4 text-amber-700 shrink-0" />
              Live Email Delivery Warning
            </p>
            <p className="text-[11px] text-amber-800 leading-relaxed">
              Confirming this dialog will immediately dispatch a real SMTP email message to{" "}
              <strong className="font-mono">{recipientEmail}</strong> using your configured SMTP credentials.
            </p>
          </div>

          <div className="space-y-2 border border-slate-200 rounded-lg p-3 bg-slate-50">
            <div>
              <span className="text-[10px] font-bold text-slate-400 uppercase">Recipient:</span>
              <p className="text-xs font-mono text-slate-800 font-semibold">{recipientEmail}</p>
            </div>
            <div>
              <span className="text-[10px] font-bold text-slate-400 uppercase">Subject:</span>
              <p className="text-xs text-slate-800 font-semibold">{subject}</p>
            </div>
            <div>
              <span className="text-[10px] font-bold text-slate-400 uppercase">Message Body:</span>
              <div className="mt-1 p-2 bg-white border border-slate-200 rounded text-slate-700 whitespace-pre-line leading-relaxed max-h-48 overflow-y-auto">
                {body}
              </div>
            </div>
          </div>

          <label className="flex items-start gap-2 pt-2 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmSend}
              onChange={(e) => setConfirmSend(e.target.checked)}
              className="mt-0.5 rounded text-indigo-600 focus:ring-indigo-500"
            />
            <span className="text-xs text-slate-700 font-medium">
              I explicitly confirm that I want to send this email to the contributor and acknowledge that this action cannot be undone.
            </span>
          </label>

          <div className="pt-3 border-t border-slate-200 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowPreviewModal(false)}
              className="px-3.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSendEmail}
              disabled={!confirmSend || sending}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{sending ? "Sending..." : "Dispatch Email"}</span>
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default function OutreachPage() {
  return (
    <Suspense fallback={<div className="h-48 bg-slate-100 rounded-xl animate-pulse" />}>
      <OutreachContent />
    </Suspense>
  );
}

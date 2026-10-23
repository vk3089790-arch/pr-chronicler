"use client";

import React, { useEffect, useState, useContext, useCallback } from "react";
import {
  Search,
  Filter,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Eye,
  BookOpen,
  Mail,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { PullRequestItem, PullRequestDetail } from "@/lib/types";
import { Badge } from "@/components/Badge";
import { Modal } from "@/components/Modal";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/LoadingSkeleton";
import { RefreshContext } from "@/components/AppShell";

export default function PullRequestsPage() {
  const { refreshKey, setIsRefreshing } = useContext(RefreshContext);
  const [items, setItems] = useState<PullRequestItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedPR, setSelectedPR] = useState<PullRequestDetail | null>(null);
  const [_detailLoading, setDetailLoading] = useState(false);

  const fetchPRs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getPullRequests({
        page,
        limit: 10,
        search: search || undefined,
        status: statusFilter || undefined,
      });
      setItems(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err) {
      console.error("Failed to fetch pull requests:", err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [page, search, statusFilter, setIsRefreshing]);

  useEffect(() => {
    fetchPRs();
  }, [fetchPRs, refreshKey]);

  const openDetail = async (deliveryId: string) => {
    setDetailLoading(true);
    try {
      const detail = await api.getPullRequestDetail(deliveryId);
      setSelectedPR(detail);
    } catch (err) {
      console.error("Failed to load PR detail:", err);
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Control Bar: Search and Filters */}
      <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by repo, title, PR #, or author..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-hidden focus:border-indigo-500 focus:bg-white transition-colors"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-700 focus:outline-hidden focus:border-indigo-500"
          >
            <option value="">All Statuses</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
            <option value="PROCESSING">Processing</option>
            <option value="IGNORED">Ignored</option>
          </select>
        </div>
      </div>

      {/* Main Table */}
      {loading ? (
        <TableSkeleton rows={8} cols={7} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No Pull Requests Found"
          description={
            search || statusFilter
              ? "No pull requests matched your search criteria. Try clearing filters."
              : "No pull requests have been processed yet. Webhooks received from GitHub will appear here."
          }
          actionText={search || statusFilter ? "Clear Filters" : undefined}
          onAction={() => {
            setSearch("");
            setStatusFilter("");
            setPage(1);
          }}
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 border-b border-slate-200/80 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">Repository & PR</th>
                  <th className="px-6 py-3.5">Title</th>
                  <th className="px-6 py-3.5">Author</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5">Learnings</th>
                  <th className="px-6 py-3.5">Email</th>
                  <th className="px-6 py-3.5">Merged / Received</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item) => (
                  <tr key={item.delivery_id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <div className="font-semibold text-slate-900">{item.repo}</div>
                      <div className="font-mono text-[11px] text-indigo-600">#{item.pr_number}</div>
                    </td>
                    <td className="px-6 py-3.5 max-w-xs">
                      <div className="truncate text-slate-800 font-medium" title={item.pr_title}>
                        {item.pr_title || `Pull Request #${item.pr_number}`}
                      </div>
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap font-mono text-[11px] text-slate-600">
                      @{item.pr_author || "unknown"}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <Badge status={item.status} size="sm" />
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      {item.learnings_count > 0 ? (
                        <span className="inline-flex items-center gap-1 font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full text-[11px]">
                          <BookOpen className="w-3 h-3" />
                          {item.learnings_count}
                        </span>
                      ) : (
                        <span className="text-slate-400 font-mono">—</span>
                      )}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <Badge variant="email" status={item.email_status} size="sm" />
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap font-mono text-[11px] text-slate-400">
                      {new Date(item.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap text-right space-x-2">
                      <button
                        onClick={() => openDetail(item.delivery_id)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors cursor-pointer"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Details
                      </button>
                      {item.pr_url && (
                        <a
                          href={item.pr_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center p-1 text-slate-400 hover:text-slate-600 transition-colors"
                          title="Open on GitHub"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="px-6 py-3.5 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <div>
              Showing <span className="font-semibold text-slate-800">{items.length}</span> of{" "}
              <span className="font-semibold text-slate-800">{total}</span> records
            </div>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-1.5 rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-mono text-xs text-slate-600">
                Page {page} of {totalPages || 1}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="p-1.5 rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Pull Request Inspection Modal */}
      {selectedPR && (
        <Modal
          isOpen={!!selectedPR}
          onClose={() => setSelectedPR(null)}
          title={`${selectedPR.repo} #${selectedPR.pr_number}`}
          subtitle={selectedPR.pr_title || `Delivery ID: ${selectedPR.delivery_id}`}
          maxWidth="3xl"
        >
          <div className="space-y-6">
            {/* Metadata Summary Banner */}
            <div className="bg-slate-50 rounded-xl p-4 border border-slate-200/80 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Processing Status</span>
                <Badge status={selectedPR.status} size="sm" className="mt-1" />
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Author</span>
                <span className="font-mono font-medium text-slate-800 mt-1 block">
                  @{selectedPR.pr_author || "unknown"}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Email Dispatch</span>
                <Badge variant="email" status={selectedPR.email_status} size="sm" className="mt-1" />
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">GitHub Link</span>
                <a
                  href={selectedPR.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-indigo-600 hover:underline mt-1 font-medium"
                >
                  View PR <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            {/* Error Banner if Failed */}
            {selectedPR.error_message && (
              <div className="bg-rose-50 border border-rose-200 text-rose-800 p-4 rounded-xl text-xs space-y-1">
                <div className="font-semibold flex items-center gap-1.5 text-rose-900">
                  <AlertCircle className="w-4 h-4 text-rose-600" />
                  Processing Failure
                </div>
                <p className="font-mono bg-white/70 p-2 rounded border border-rose-100">
                  {selectedPR.error_message}
                </p>
              </div>
            )}

            {/* Reflection Content if Available */}
            {selectedPR.reflection ? (
              <div className="space-y-5">
                {/* Issue Details */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Issue Details & Problem Addressed
                  </h4>
                  <div className="bg-slate-50/70 p-3.5 rounded-xl border border-slate-200/80 text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
                    {selectedPR.reflection.issue_details}
                  </div>
                </div>

                {/* Execution Summary */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Execution Summary & Architecture Changes
                  </h4>
                  <div className="bg-slate-50/70 p-3.5 rounded-xl border border-slate-200/80 text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
                    {selectedPR.reflection.execution_summary}
                  </div>
                </div>

                {/* Key Learnings */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-indigo-600" />
                    Key Learnings ({selectedPR.reflection.key_learnings.length})
                  </h4>
                  <div className="space-y-2">
                    {selectedPR.reflection.key_learnings.map((learning, idx) => (
                      <div
                        key={idx}
                        className="bg-white border border-slate-200/80 rounded-xl p-3.5 text-xs text-slate-800 shadow-2xs leading-relaxed"
                      >
                        <span className="font-semibold text-indigo-600 mr-2">{idx + 1}.</span>
                        {learning}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : selectedPR.status === "COMPLETED" ? (
              <div className="p-6 text-center text-xs text-slate-400 bg-slate-50 rounded-xl">
                Reflection JSON payload was not formatted as standard structured output.
              </div>
            ) : (
              <div className="p-6 text-center text-xs text-slate-500 bg-slate-50 rounded-xl">
                Reflection not generated for this pull request (Status: {selectedPR.status}).
                {selectedPR.reason && <p className="mt-1 font-mono">{selectedPR.reason}</p>}
              </div>
            )}

            {/* Email Dispatch Audit History */}
            {selectedPR.emails && selectedPR.emails.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-slate-500" />
                  Email Delivery Log
                </h4>
                <div className="divide-y divide-slate-100 rounded-lg border border-slate-200/80 overflow-hidden text-xs">
                  {selectedPR.emails.map((e) => (
                    <div key={e.id} className="p-3 bg-slate-50/50 flex items-center justify-between">
                      <div>
                        <div className="font-medium text-slate-900">{e.subject}</div>
                        <div className="text-slate-500 text-[11px] font-mono mt-0.5">
                          Recipient: {e.recipient}
                        </div>
                      </div>
                      <div className="text-right">
                        <Badge variant="email" status={e.status} size="sm" />
                        <div className="text-[10px] text-slate-400 font-mono mt-1">
                          {new Date(e.sent_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

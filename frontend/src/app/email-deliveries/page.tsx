"use client";

import React, { useEffect, useState, useContext, useCallback } from "react";
import {
  Search,
  Filter,
  Eye,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { EmailDeliveryItem } from "@/lib/types";
import { Badge } from "@/components/Badge";
import { Modal } from "@/components/Modal";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/LoadingSkeleton";
import { RefreshContext } from "@/components/AppShell";

export default function EmailDeliveriesPage() {
  const { refreshKey, setIsRefreshing } = useContext(RefreshContext);
  const [items, setItems] = useState<EmailDeliveryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedEmail, setSelectedEmail] = useState<EmailDeliveryItem | null>(null);

  const fetchEmails = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getEmailDeliveries({
        page,
        limit: 10,
        status: statusFilter || undefined,
        search: search || undefined,
      });
      setItems(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err) {
      console.error("Failed to fetch email deliveries:", err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [page, statusFilter, search, setIsRefreshing]);

  useEffect(() => {
    fetchEmails();
  }, [fetchEmails, refreshKey]);

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Privacy Notice Banner */}
      <div className="bg-indigo-50/60 border border-indigo-100 rounded-xl p-4 flex items-center gap-3 text-xs text-indigo-900">
        <ShieldCheck className="w-5 h-5 text-indigo-600 shrink-0" />
        <div>
          <span className="font-semibold">Recipient Privacy Protected:</span> All recipient email addresses
          are masked at the backend query layer before transmission to the browser.
        </div>
      </div>

      {/* Control Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search repo, subject, delivery ID..."
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
            <option value="">All Delivery Statuses</option>
            <option value="SENT">Sent</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
      </div>

      {/* Emails Table */}
      {loading ? (
        <TableSkeleton rows={6} cols={6} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No Email Deliveries Found"
          description="SMTP report dispatches triggered by merged PR reflections will be logged here."
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
                  <th className="px-6 py-3.5">Subject</th>
                  <th className="px-6 py-3.5">Repository & PR</th>
                  <th className="px-6 py-3.5">Recipient</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5">Sent Timestamp</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-3.5 max-w-sm">
                      <div className="font-semibold text-slate-900 truncate" title={item.subject}>
                        {item.subject}
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono truncate">
                        ID: {item.delivery_id}
                      </div>
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <span className="font-medium text-slate-800">{item.repo}</span>
                      <span className="text-indigo-600 font-mono ml-1">#{item.pr_number}</span>
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap font-mono text-[11px] text-slate-700">
                      {item.recipient}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <Badge variant="email" status={item.status} size="sm" />
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap font-mono text-[11px] text-slate-400">
                      {new Date(item.sent_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap text-right">
                      <button
                        onClick={() => setSelectedEmail(item)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors cursor-pointer"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
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

      {/* Email Modal */}
      {selectedEmail && (
        <Modal
          isOpen={!!selectedEmail}
          onClose={() => setSelectedEmail(null)}
          title="Email Dispatch Record"
          subtitle={selectedEmail.subject}
          maxWidth="2xl"
        >
          <div className="space-y-4">
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Recipient</span>
                <span className="font-mono font-medium text-slate-900 mt-1 block">
                  {selectedEmail.recipient}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Delivery Status</span>
                <Badge variant="email" status={selectedEmail.status} size="sm" className="mt-1" />
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Related Repository & PR</span>
                <span className="font-semibold text-slate-900 mt-1 block">
                  {selectedEmail.repo} #{selectedEmail.pr_number}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Sent Timestamp</span>
                <span className="font-mono text-slate-800 mt-1 block">
                  {new Date(selectedEmail.sent_at).toISOString()}
                </span>
              </div>
            </div>

            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200/80 text-xs space-y-1">
              <span className="font-semibold text-slate-700 block">Exact Subject Line:</span>
              <p className="font-mono text-slate-800 bg-white p-2 rounded border border-slate-200">
                {selectedEmail.subject}
              </p>
            </div>

            {selectedEmail.error_message && (
              <div className="bg-rose-50 border border-rose-200 p-3.5 rounded-xl text-xs space-y-1">
                <span className="font-semibold text-rose-900 flex items-center gap-1.5">
                  <AlertCircle className="w-4 h-4 text-rose-600" />
                  SMTP Transmission Error
                </span>
                <p className="text-rose-800 font-mono text-[11px] bg-white/70 p-2 rounded border border-rose-100 whitespace-pre-wrap">
                  {selectedEmail.error_message}
                </p>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

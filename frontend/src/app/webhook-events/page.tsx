"use client";

import React, { useEffect, useState, useContext, useCallback } from "react";
import {
  Search,
  Filter,
  Eye,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { WebhookEventItem } from "@/lib/types";
import { Badge } from "@/components/Badge";
import { Modal } from "@/components/Modal";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/LoadingSkeleton";
import { RefreshContext } from "@/components/AppShell";

export default function WebhookEventsPage() {
  const { refreshKey, setIsRefreshing } = useContext(RefreshContext);
  const [items, setItems] = useState<WebhookEventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<WebhookEventItem | null>(null);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getWebhookEvents({
        page,
        limit: 10,
        status: statusFilter || undefined,
        search: search || undefined,
      });
      setItems(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err) {
      console.error("Failed to fetch webhook events:", err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [page, statusFilter, search, setIsRefreshing]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents, refreshKey]);

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Control Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search delivery ID, repo, reason..."
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
            <option value="">All Event Statuses</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
            <option value="PROCESSING">Processing</option>
            <option value="IGNORED">Ignored</option>
          </select>
        </div>
      </div>

      {/* Events Table */}
      {loading ? (
        <TableSkeleton rows={8} cols={6} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No Webhook Events Found"
          description="Inbound webhook events received from GitHub will be logged here."
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
                  <th className="px-6 py-3.5">Delivery ID</th>
                  <th className="px-6 py-3.5">Repository & PR</th>
                  <th className="px-6 py-3.5">Action</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5">Received At</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                {items.map((item) => (
                  <tr key={item.delivery_id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-3.5 text-slate-900 font-medium">
                      <span className="truncate max-w-[160px] inline-block" title={item.delivery_id}>
                        {item.delivery_id}
                      </span>
                    </td>
                    <td className="px-6 py-3.5 font-sans">
                      <div className="font-semibold text-slate-900">{item.repo}</div>
                      <div className="text-indigo-600 font-mono text-[11px]">#{item.pr_number}</div>
                    </td>
                    <td className="px-6 py-3.5">
                      <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-[10px]">
                        {item.action}
                      </span>
                    </td>
                    <td className="px-6 py-3.5 font-sans">
                      <Badge status={item.status} size="sm" />
                    </td>
                    <td className="px-6 py-3.5 text-slate-400">
                      {new Date(item.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-6 py-3.5 text-right font-sans">
                      <button
                        onClick={() => setSelectedEvent(item)}
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
              <span className="font-semibold text-slate-800">{total}</span> events
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

      {/* Event Details Modal */}
      {selectedEvent && (
        <Modal
          isOpen={!!selectedEvent}
          onClose={() => setSelectedEvent(null)}
          title="Webhook Delivery Audit"
          subtitle={`Delivery ID: ${selectedEvent.delivery_id}`}
          maxWidth="2xl"
        >
          <div className="space-y-4">
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Repository & PR</span>
                <span className="font-semibold text-slate-900 mt-1 block">
                  {selectedEvent.repo} #{selectedEvent.pr_number}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Audit Status</span>
                <Badge status={selectedEvent.status} size="sm" className="mt-1" />
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">GitHub Action</span>
                <span className="font-mono text-slate-800 mt-1 block">{selectedEvent.action}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Received Timestamp</span>
                <span className="font-mono text-slate-800 mt-1 block">
                  {new Date(selectedEvent.created_at).toISOString()}
                </span>
              </div>
            </div>

            {selectedEvent.reason && (
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200/80 text-xs">
                <span className="font-semibold text-slate-700 block mb-1">Audit Reason / Note:</span>
                <p className="text-slate-600 font-mono text-[11px]">{selectedEvent.reason}</p>
              </div>
            )}

            {selectedEvent.error_message && (
              <div className="bg-rose-50 border border-rose-200 p-3.5 rounded-xl text-xs space-y-1">
                <span className="font-semibold text-rose-900 flex items-center gap-1.5">
                  <AlertCircle className="w-4 h-4 text-rose-600" />
                  Failure Traceback
                </span>
                <p className="text-rose-800 font-mono text-[11px] bg-white/70 p-2 rounded border border-rose-100 whitespace-pre-wrap">
                  {selectedEvent.error_message}
                </p>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

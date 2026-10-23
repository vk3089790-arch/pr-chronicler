"use client";

import React, { useEffect, useState, useContext, useCallback } from "react";
import {
  Search,
  Copy,
  Check,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  FileText,
} from "lucide-react";
import { api } from "@/lib/api";
import { LearningItem } from "@/lib/types";
import { Badge } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { Modal } from "@/components/Modal";
import { RefreshContext } from "@/components/AppShell";

export default function LearningsPage() {
  const { refreshKey, setIsRefreshing } = useContext(RefreshContext);
  const [items, setItems] = useState<LearningItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [selectedLearning, setSelectedLearning] = useState<LearningItem | null>(null);

  const fetchLearnings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getLearnings({
        page,
        limit: 10,
        search: search || undefined,
      });
      setItems(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err) {
      console.error("Failed to fetch learnings:", err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [page, search, setIsRefreshing]);

  useEffect(() => {
    fetchLearnings();
  }, [fetchLearnings, refreshKey]);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Header Controls */}
      <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search key takeaways, concepts, or repos..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-hidden focus:border-indigo-500 focus:bg-white transition-colors"
          />
        </div>

        <div className="text-xs text-slate-500 font-mono">
          Showing {items.length} of {total} extracted learnings
        </div>
      </div>

      {/* Learnings Grid / List */}
      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200/80 p-5 space-y-3">
              <div className="h-4 w-48 bg-slate-100 rounded animate-pulse" />
              <div className="h-12 w-full bg-slate-50 rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No Key Learnings Found"
          description={
            search
              ? "No learnings matched your search. Try different keywords."
              : "No key learnings have been extracted yet. When pull requests are merged, Gemini extracts 3-4 takeaways."
          }
          actionText={search ? "Clear Search" : undefined}
          onAction={() => {
            setSearch("");
            setPage(1);
          }}
        />
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs hover:border-slate-300 transition-all flex flex-col justify-between gap-4"
            >
              <div>
                {/* Header info */}
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-slate-900">{item.repo}</span>
                    <a
                      href={item.pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-xs text-indigo-600 hover:underline flex items-center gap-0.5"
                    >
                      #{item.pr_number}
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                    <span className="text-slate-300">•</span>
                    <span className="text-xs text-slate-500 line-clamp-1 max-w-xs">
                      {item.pr_title}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {item.evidence_tags.map((tag) => (
                      <Badge key={tag} variant="evidence" size="sm">
                        [{tag}]
                      </Badge>
                    ))}
                    <button
                      onClick={() => handleCopy(item.id, item.learning)}
                      className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
                      title="Copy takeaway to clipboard"
                    >
                      {copiedId === item.id ? (
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Learning text */}
                <p className="text-xs text-slate-800 leading-relaxed font-normal whitespace-pre-wrap">
                  {item.learning}
                </p>
              </div>

              {/* Footer with view context action */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                <time className="font-mono">
                  Extracted {new Date(item.created_at).toLocaleDateString()}
                </time>
                <button
                  onClick={() => setSelectedLearning(item)}
                  className="font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1 cursor-pointer"
                >
                  <FileText className="w-3.5 h-3.5" />
                  View Full PR Context
                </button>
              </div>
            </div>
          ))}

          {/* Pagination */}
          <div className="bg-white rounded-xl border border-slate-200/80 px-6 py-3.5 flex items-center justify-between text-xs text-slate-500 shadow-xs">
            <div>
              Showing <span className="font-semibold text-slate-800">{items.length}</span> of{" "}
              <span className="font-semibold text-slate-800">{total}</span> learnings
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

      {/* Context Inspection Modal */}
      {selectedLearning && (
        <Modal
          isOpen={!!selectedLearning}
          onClose={() => setSelectedLearning(null)}
          title={`Context: ${selectedLearning.repo} #${selectedLearning.pr_number}`}
          subtitle={selectedLearning.pr_title}
          maxWidth="2xl"
        >
          <div className="space-y-4">
            <div className="bg-indigo-50/60 p-4 rounded-xl border border-indigo-100 text-xs space-y-1">
              <span className="font-semibold text-indigo-900 block">Selected Takeaway</span>
              <p className="text-indigo-950 font-medium leading-relaxed">
                {selectedLearning.learning}
              </p>
            </div>

            {selectedLearning.issue_details_snippet && (
              <div className="space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Issue Details Context
                </span>
                <p className="text-xs text-slate-700 bg-slate-50 p-3 rounded-lg border border-slate-200/80 leading-relaxed">
                  {selectedLearning.issue_details_snippet}
                </p>
              </div>
            )}

            {selectedLearning.execution_summary_snippet && (
              <div className="space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Execution Summary Context
                </span>
                <p className="text-xs text-slate-700 bg-slate-50 p-3 rounded-lg border border-slate-200/80 leading-relaxed">
                  {selectedLearning.execution_summary_snippet}
                </p>
              </div>
            )}

            <div className="pt-2 flex justify-end">
              <a
                href={selectedLearning.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors"
              >
                Open PR on GitHub <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

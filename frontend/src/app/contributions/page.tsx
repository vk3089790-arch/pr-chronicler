"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  GitPullRequest,
  Sparkles,
  Bookmark,
  BookmarkCheck,
  Search,
} from "lucide-react";
import { api } from "@/lib/api";
import { SavedContributionItem } from "@/lib/types";

export default function ContributionsCatalogPage() {
  const [items, setItems] = useState<SavedContributionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [savedOnly, setSavedOnly] = useState(false);
  const [analyzedOnly, setAnalyzedOnly] = useState(false);
  const [page, setPage] = useState(1);

  const fetchContributions = useCallback(() => {
    setLoading(true);
    api.getExplorerContributions({
      page,
      limit: 20,
      search: search.trim() || undefined,
      saved_only: savedOnly || undefined,
      analyzed_only: analyzedOnly || undefined,
    })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [page, search, savedOnly, analyzedOnly]);

  useEffect(() => {
    fetchContributions();
  }, [fetchContributions]);

  const handleToggleBookmark = async (item: SavedContributionItem) => {
    try {
      const nextSaved = !item.is_saved;
      await api.saveContributionBookmark(item.repo, item.pr_number, nextSaved);
      setItems((prev) =>
        prev.map((i) => (i.id === item.id ? { ...i, is_saved: nextSaved } : i))
      );
    } catch {
      // ignore
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 mb-2 text-indigo-600">
            <GitPullRequest className="w-5 h-5" />
            <h2 className="text-xl font-bold tracking-tight text-slate-900">
              Open-Source Contributions
            </h2>
          </div>
          <p className="text-sm text-slate-600">
            Catalog of analyzed pull requests, saved bookmarks, and AI engineering reflections.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative flex-1 w-full sm:max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by repo, author, or PR title..."
            className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setSavedOnly(!savedOnly)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer ${
              savedOnly
                ? "bg-amber-100 text-amber-900 border border-amber-300"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            <Bookmark className="w-3.5 h-3.5" />
            Saved Only
          </button>

          <button
            onClick={() => setAnalyzedOnly(!analyzedOnly)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer ${
              analyzedOnly
                ? "bg-indigo-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            AI Analyzed
          </button>

          <span className="text-xs text-slate-400 font-mono pl-2">
            Total: {total}
          </span>
        </div>
      </div>

      {/* Contributions Table / List */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white p-12 rounded-xl border border-slate-200 text-center text-xs text-slate-500 space-y-3">
          <p>No contributions match your filters.</p>
          <Link
            href="/"
            className="inline-block px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors"
          >
            Explore Repositories or Contributors
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200/80 divide-y divide-slate-100 shadow-xs overflow-hidden">
          {items.map((item) => {
            const [owner, repo] = item.repo.split("/");
            return (
              <div
                key={item.id}
                className="p-5 hover:bg-slate-50/80 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="min-w-0 space-y-1.5 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-bold text-slate-900">{item.repo}</span>
                    <span className="text-xs font-mono text-indigo-600">#{item.pr_number}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-purple-100 text-purple-800 border border-purple-200">
                      {item.state}
                    </span>

                    {item.is_analyzed && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        Reflected
                      </span>
                    )}
                  </div>

                  <h4 className="text-sm font-semibold text-slate-800 leading-snug">
                    {item.pr_title}
                  </h4>

                  <div className="flex items-center gap-4 text-[11px] text-slate-400">
                    <Link
                      href={`/profiles/${item.pr_author}`}
                      className="text-slate-600 hover:text-indigo-600 font-medium"
                    >
                      by @{item.pr_author}
                    </Link>
                    <span>
                      Updated{" "}
                      {new Date(item.updated_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleToggleBookmark(item)}
                    className={`p-2 rounded-lg border transition-colors cursor-pointer ${
                      item.is_saved
                        ? "bg-amber-50 text-amber-600 border-amber-200"
                        : "bg-slate-50 text-slate-400 border-slate-200 hover:text-slate-600"
                    }`}
                    title={item.is_saved ? "Remove bookmark" : "Save bookmark"}
                  >
                    {item.is_saved ? (
                      <BookmarkCheck className="w-4 h-4" />
                    ) : (
                      <Bookmark className="w-4 h-4" />
                    )}
                  </button>

                  <Link
                    href={`/contributions/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${item.pr_number}`}
                    className="px-3.5 py-2 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Inspect Details
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

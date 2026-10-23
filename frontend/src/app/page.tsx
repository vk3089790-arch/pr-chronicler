"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Search,
  User,
  FolderGit2,
  Sparkles,
  ArrowRight,
  Clock,
  Compass,
  Mail,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { RecentSearchItem, SavedContributionItem } from "@/lib/types";

const EXAMPLE_SEARCHES = [
  { label: "tiangolo (FastAPI)", query: "tiangolo", type: "user" },
  { label: "torvalds (Linux)", query: "torvalds", type: "user" },
  { label: "fastapi/fastapi", query: "fastapi/fastapi", type: "repo" },
  { label: "pallets/flask", query: "pallets/flask", type: "repo" },
  { label: "langchain-ai/langchain", query: "langchain-ai/langchain", type: "repo" },
];

export default function ExplorePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"auto" | "user" | "repo">("auto");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentSearches, setRecentSearches] = useState<RecentSearchItem[]>([]);
  const [savedContributions, setSavedContributions] = useState<SavedContributionItem[]>([]);

  useEffect(() => {
    // Load recent searches & analyzed contributions
    api.getRecentSearches(6).then(setRecentSearches).catch(() => {});
    api.getExplorerContributions({ limit: 4, analyzed_only: true })
      .then((res) => setSavedContributions(res.items))
      .catch(() => {});
  }, []);

  const handleSearch = async (e?: React.FormEvent, directQuery?: string, directType?: string) => {
    if (e) e.preventDefault();
    const q = (directQuery ?? query).trim();
    if (!q) {
      setError("Please enter a GitHub username, profile URL, or repository URL.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const modeParam = directType || (searchMode === "auto" ? undefined : searchMode);
      const res = await api.searchExplorer(q, modeParam);

      if (res.mode === "user") {
        router.push(`/profiles/${encodeURIComponent(res.identifier1)}`);
      } else {
        router.push(`/repositories/${encodeURIComponent(res.identifier1)}/${encodeURIComponent(res.identifier2 || "")}`);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to parse search query";
      setError(message);
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* Hero Banner with Search */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 border border-slate-800 p-8 sm:p-12 shadow-xl">
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-3xl mx-auto text-center space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI-Powered Open-Source Intelligence</span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Discover GitHub Contributions & Technical Learnings
          </h1>

          <p className="text-slate-300 text-sm sm:text-base leading-relaxed max-w-2xl mx-auto">
            Explore open-source pull requests, analyze engineering decisions with Gemini,
            and connect with passionate contributors through verified email outreach.
          </p>

          {/* Search Mode Toggles */}
          <div className="pt-4 flex justify-center">
            <div className="inline-flex p-1 bg-slate-800/80 rounded-xl border border-slate-700/60 shadow-inner">
              <button
                type="button"
                onClick={() => setSearchMode("auto")}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  searchMode === "auto"
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Auto-Detect
              </button>
              <button
                type="button"
                onClick={() => setSearchMode("user")}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  searchMode === "user"
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <User className="w-3.5 h-3.5" />
                Contributor
              </button>
              <button
                type="button"
                onClick={() => setSearchMode("repo")}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  searchMode === "repo"
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <FolderGit2 className="w-3.5 h-3.5" />
                Repository
              </button>
            </div>
          </div>

          {/* Main Search Input Form */}
          <form onSubmit={handleSearch} className="pt-2 max-w-2xl mx-auto">
            <div className="relative flex items-center">
              <div className="absolute left-4 pointer-events-none text-slate-400">
                <Search className="w-5 h-5" />
              </div>
              <input
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  if (error) setError(null);
                }}
                placeholder={
                  searchMode === "user"
                    ? "Enter username or profile URL (e.g. torvalds or https://github.com/torvalds)"
                    : searchMode === "repo"
                    ? "Enter repository or URL (e.g. fastapi/fastapi or https://github.com/fastapi/fastapi)"
                    : "Enter username, profile URL, or repository (e.g. tiangolo or pallets/flask)"
                }
                className="w-full pl-12 pr-32 py-4 bg-slate-900/90 border-2 border-indigo-500/30 rounded-xl text-white placeholder-slate-400 text-sm focus:outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/20 shadow-lg transition-all"
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="absolute right-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-all flex items-center gap-2 shadow-md cursor-pointer"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <span>Explore</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="mt-3 flex items-center justify-center gap-1.5 text-xs text-rose-400 font-medium">
                <AlertCircle className="w-4 h-4" />
                <span>{error}</span>
              </div>
            )}
          </form>

          {/* Quick Example Chips */}
          <div className="pt-4 flex flex-wrap items-center justify-center gap-2">
            <span className="text-xs text-slate-400">Try exploring:</span>
            {EXAMPLE_SEARCHES.map((ex) => (
              <button
                key={ex.query}
                type="button"
                onClick={() => {
                  setQuery(ex.query);
                  handleSearch(undefined, ex.query, ex.type);
                }}
                className="px-2.5 py-1 text-xs bg-slate-800/70 hover:bg-slate-700/80 text-slate-300 hover:text-white rounded-md border border-slate-700/60 transition-colors"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Two Column Grid: Recent Searches & AI Learnings Showcase */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (1 span): Recent Search History */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-600" />
              <h3 className="text-sm font-semibold text-slate-900">Recent Searches</h3>
            </div>
            <span className="text-[11px] text-slate-400 font-mono">SQLite WAL</span>
          </div>

          <div className="divide-y divide-slate-100 mt-2 flex-1">
            {recentSearches.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">
                No recent searches yet. Try searching for a GitHub contributor or repo above!
              </div>
            ) : (
              recentSearches.map((item) => (
                <div
                  key={item.id}
                  className="py-3 flex items-center justify-between hover:bg-slate-50/80 px-2 rounded-lg transition-colors cursor-pointer"
                  onClick={() => {
                    if (item.search_type === "user") {
                      router.push(`/profiles/${encodeURIComponent(item.target)}`);
                    } else {
                      const [owner, repo] = item.target.split("/");
                      router.push(`/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`);
                    }
                  }}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="p-1.5 rounded-md bg-slate-100 text-slate-600">
                      {item.search_type === "user" ? (
                        <User className="w-3.5 h-3.5" />
                      ) : (
                        <FolderGit2 className="w-3.5 h-3.5" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-800 truncate">{item.target}</p>
                      <p className="text-[10px] text-slate-400 capitalize">{item.search_type}</p>
                    </div>
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Column (2 spans): Recently Analyzed Contributions */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              <h3 className="text-sm font-semibold text-slate-900">Analyzed Open-Source Contributions</h3>
            </div>
            <Link
              href="/contributions"
              className="text-xs font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
            >
              View all contributions <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="divide-y divide-slate-100 mt-2 flex-1">
            {savedContributions.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-400">
                No contributions analyzed yet. Search a contributor or repository to generate your first reflection!
              </div>
            ) : (
              savedContributions.map((c) => {
                const [owner, repo] = c.repo.split("/");
                return (
                  <div
                    key={c.id}
                    className="py-3.5 px-2 hover:bg-slate-50/80 rounded-lg transition-colors flex items-start justify-between gap-4"
                  >
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-slate-900 truncate">
                          {c.repo}
                        </span>
                        <span className="text-xs text-indigo-600 font-mono">#{c.pr_number}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Analyzed
                        </span>
                      </div>
                      <p className="text-xs text-slate-700 font-medium truncate">{c.pr_title}</p>
                      <div className="flex items-center gap-3 text-[11px] text-slate-400">
                        <span>By @{c.pr_author}</span>
                        {c.analyzed_at && (
                          <span>
                            Analyzed{" "}
                            {new Date(c.analyzed_at).toLocaleDateString(undefined, {
                              month: "short",
                              day: "numeric",
                            })}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Link
                        href={`/contributions/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${c.pr_number}`}
                        className="px-3 py-1.5 text-xs font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg transition-colors"
                      >
                        Inspect & Reflection
                      </Link>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Feature Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link
          href="/profiles"
          className="p-5 rounded-xl bg-white border border-slate-200/80 hover:border-indigo-400 hover:shadow-md transition-all group"
        >
          <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
            <User className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-semibold text-slate-900 group-hover:text-indigo-600">
            Contributor Profiles
          </h4>
          <p className="text-xs text-slate-500 mt-1">
            Search developers, review their public PRs, primary languages, and activity.
          </p>
        </Link>

        <Link
          href="/repositories"
          className="p-5 rounded-xl bg-white border border-slate-200/80 hover:border-indigo-400 hover:shadow-md transition-all group"
        >
          <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
            <FolderGit2 className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-semibold text-slate-900 group-hover:text-emerald-600">
            Repository Explorer
          </h4>
          <p className="text-xs text-slate-500 mt-1">
            Inspect top contributors, pull requests, merged code changes, and tech stacks.
          </p>
        </Link>

        <Link
          href="/outreach"
          className="p-5 rounded-xl bg-white border border-slate-200/80 hover:border-indigo-400 hover:shadow-md transition-all group"
        >
          <div className="w-9 h-9 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
            <Mail className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-semibold text-slate-900 group-hover:text-amber-600">
            Contributor Outreach
          </h4>
          <p className="text-xs text-slate-500 mt-1">
            Draft personalized outreach emails referencing technical contributions with privacy safeguards.
          </p>
        </Link>

        <Link
          href="/webhook-automation"
          className="p-5 rounded-xl bg-white border border-slate-200/80 hover:border-indigo-400 hover:shadow-md transition-all group"
        >
          <div className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
            <Compass className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-semibold text-slate-900 group-hover:text-purple-600">
            Webhook Automation
          </h4>
          <p className="text-xs text-slate-500 mt-1">
            View automated merged-PR pipeline metrics, HMAC delivery verification, and health logs.
          </p>
        </Link>
      </div>
    </div>
  );
}

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  FolderGit2,
  GitPullRequest,
  Users,
  ExternalLink,
  Sparkles,
  AlertCircle,
  Filter,
  User,
  Mail,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { ContributorProfile, ExplorerPRItem, RepositoryMetadata } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";

function RepositoryDetailPageContent() {
  const params = useParams();
  const router = useRouter();
  const owner = decodeURIComponent(String(params.owner || ""));
  const repo = decodeURIComponent(String(params.repo || ""));

  const [meta, setMeta] = useState<RepositoryMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"prs" | "contributors">("prs");

  // PRs State
  const [prs, setPrs] = useState<ExplorerPRItem[]>([]);
  const [prsLoading, setPrsLoading] = useState(true);
  const [prStateFilter, setPrStateFilter] = useState("all");
  const [prPage, setPrPage] = useState(1);

  // Contributors State
  const [contributors, setContributors] = useState<ContributorProfile[]>([]);
  const [contribsLoading, setContribsLoading] = useState(false);

  // Load Repo Metadata
  useEffect(() => {
    if (!owner || !repo) return;
    setLoading(true);
    setError(null);

    api.getRepositoryMetadata(owner, repo)
      .then((data) => setMeta(data))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setError(`Repository '${owner}/${repo}' was not found on GitHub.`);
        } else {
          setError(err.message || "Failed to load repository metadata");
        }
      })
      .finally(() => setLoading(false));
  }, [owner, repo]);

  // Load Pull Requests
  const fetchPRs = useCallback(() => {
    if (!owner || !repo) return;
    setPrsLoading(true);
    api.getRepositoryPullRequests(owner, repo, prStateFilter, prPage, 30)
      .then((data) => setPrs(data))
      .catch(() => setPrs([]))
      .finally(() => setPrsLoading(false));
  }, [owner, repo, prStateFilter, prPage]);

  useEffect(() => {
    if (activeTab === "prs") {
      fetchPRs();
    }
  }, [activeTab, fetchPRs]);

  // Load Contributors
  useEffect(() => {
    if (activeTab === "contributors" && owner && repo) {
      setContribsLoading(true);
      api.getRepositoryContributors(owner, repo, 1, 30)
        .then((data) => setContributors(data))
        .catch(() => setContributors([]))
        .finally(() => setContribsLoading(false));
    }
  }, [activeTab, owner, repo]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-44 bg-slate-200 rounded-xl" />
        <div className="h-64 bg-slate-100 rounded-xl" />
      </div>
    );
  }

  if (error || !meta) {
    return (
      <EmptyState
        title="Repository Not Found"
        description={error || `Repository '${owner}/${repo}' does not exist or is private.`}
        icon={AlertCircle}
        actionText="Browse Repositories"
        onAction={() => router.push("/repositories")}
      />
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Repository Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <FolderGit2 className="w-5 h-5 text-indigo-600" />
              <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                {meta.full_name}
              </h2>
            </div>

            <p className="text-xs sm:text-sm text-slate-600 max-w-2xl leading-relaxed">
              {meta.description || "No repository description provided."}
            </p>

            {/* Topics */}
            {meta.topics && meta.topics.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {meta.topics.map((t) => (
                  <span
                    key={t}
                    className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700"
                  >
                    #{t}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <a
              href={meta.html_url}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View on GitHub
            </a>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-slate-100">
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-[11px] font-medium text-slate-500">Stars</span>
            <p className="text-lg font-bold text-slate-900 mt-0.5">
              ★ {meta.stargazers_count.toLocaleString()}
            </p>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-[11px] font-medium text-slate-500">Forks</span>
            <p className="text-lg font-bold text-slate-900 mt-0.5">
              {meta.forks_count.toLocaleString()}
            </p>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-[11px] font-medium text-slate-500">Primary Language</span>
            <p className="text-sm font-bold text-slate-900 mt-1 truncate">
              {meta.language || "Not specified"}
            </p>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-[11px] font-medium text-slate-500">Open Issues</span>
            <p className="text-lg font-bold text-slate-900 mt-0.5">
              {meta.open_issues_count.toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 gap-6 text-sm font-medium">
        <button
          onClick={() => setActiveTab("prs")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeTab === "prs"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <GitPullRequest className="w-4 h-4" />
          Pull Requests
        </button>

        <button
          onClick={() => setActiveTab("contributors")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeTab === "contributors"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Users className="w-4 h-4" />
          Top Contributors
        </button>
      </div>

      {/* Tab 1: Pull Requests */}
      {activeTab === "prs" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3 bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-400" />
              <span className="text-xs font-semibold text-slate-700">PR State:</span>
              <div className="flex gap-1">
                {(["all", "open", "closed"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      setPrStateFilter(s);
                      setPrPage(1);
                    }}
                    className={`px-3 py-1 text-xs font-semibold rounded-md capitalize transition-colors ${
                      prStateFilter === s
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <span className="text-xs text-slate-400 font-mono">
              Showing {prs.length} pull requests
            </span>
          </div>

          {prsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : prs.length === 0 ? (
            <div className="bg-white p-8 rounded-xl border border-slate-200 text-center text-xs text-slate-500">
              No pull requests found matching the selected state.
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200/80 divide-y divide-slate-100 shadow-xs overflow-hidden">
              {prs.map((pr) => (
                <div
                  key={pr.number}
                  className="p-5 hover:bg-slate-50/80 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="min-w-0 space-y-1.5 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-indigo-600 font-bold">
                        #{pr.number}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                          pr.state === "merged" || pr.merged_at
                            ? "bg-purple-100 text-purple-800 border border-purple-200"
                            : pr.state === "open"
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                            : "bg-slate-100 text-slate-600 border border-slate-200"
                        }`}
                      >
                        {pr.merged_at ? "merged" : pr.state}
                      </span>

                      {pr.is_analyzed && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                          <Sparkles className="w-3 h-3" />
                          AI Analyzed
                        </span>
                      )}
                    </div>

                    <h4 className="text-sm font-semibold text-slate-800 leading-snug truncate">
                      {pr.title}
                    </h4>

                    <div className="flex items-center gap-4 text-[11px] text-slate-400">
                      {pr.user && (
                        <Link
                          href={`/profiles/${pr.user.login}`}
                          className="text-slate-600 hover:text-indigo-600 font-medium"
                        >
                          by @{pr.user.login}
                        </Link>
                      )}
                      <span>
                        Created{" "}
                        {new Date(pr.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Link
                      href={`/contributions/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${pr.number}`}
                      className="px-3.5 py-2 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      Inspect & Analyze
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Top Contributors */}
      {activeTab === "contributors" && (
        <div className="space-y-4">
          {contribsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : contributors.length === 0 ? (
            <div className="bg-white p-8 rounded-xl border border-slate-200 text-center text-xs text-slate-500">
              No contributors retrieved for this repository.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {contributors.map((c) => (
                <div
                  key={c.login}
                  className="p-4 bg-white rounded-xl border border-slate-200/80 shadow-xs flex items-center justify-between gap-3 hover:border-indigo-300 transition-all"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {c.avatar_url ? (
                      <img
                        src={c.avatar_url}
                        alt={c.login}
                        className="w-10 h-10 rounded-full border border-slate-200 object-cover shrink-0"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center shrink-0">
                        <User className="w-5 h-5 text-slate-500" />
                      </div>
                    )}
                    <div className="min-w-0">
                      <Link
                        href={`/profiles/${c.login}`}
                        className="text-xs font-bold text-slate-900 hover:text-indigo-600 truncate block"
                      >
                        @{c.login}
                      </Link>
                      <p className="text-[11px] text-slate-400">Contributor</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <Link
                      href={`/outreach?username=${encodeURIComponent(c.login)}&repo=${encodeURIComponent(
                        meta.full_name
                      )}`}
                      className="p-2 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 transition-colors"
                      title="Compose Outreach"
                    >
                      <Mail className="w-4 h-4" />
                    </Link>
                    <Link
                      href={`/profiles/${c.login}`}
                      className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
                      title="View Profile"
                    >
                      <User className="w-4 h-4" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function RepositoryDetailPage() {
  return (
    <React.Suspense fallback={<div className="h-48 bg-slate-100 rounded-xl animate-pulse" />}>
      <RepositoryDetailPageContent />
    </React.Suspense>
  );
}

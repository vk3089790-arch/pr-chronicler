"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Sparkles,
  ExternalLink,
  FolderGit2,
  Bookmark,
  BookmarkCheck,
  Mail,
  FileCode2,
  AlertCircle,
  RotateCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { ExplorerPRDetail } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";

function ContributionDetailPageContent() {
  const params = useParams();
  const router = useRouter();
  const owner = decodeURIComponent(String(params.owner || ""));
  const repo = decodeURIComponent(String(params.repo || ""));
  const prNumber = parseInt(String(params.prNumber || "0"), 10);

  const [detail, setDetail] = useState<ExplorerPRDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Analysis state
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Saved / Bookmark state
  const [isSaved, setIsSaved] = useState(false);

  // Patch viewer toggle
  const [expandedFiles, setExpandedFiles] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!owner || !repo || !prNumber) return;
    setLoading(true);
    setError(null);

    api.getPRExploration(owner, repo, prNumber)
      .then((data) => {
        setDetail(data);
        setIsSaved(data.is_saved);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setError(`Pull request #${prNumber} in '${owner}/${repo}' was not found.`);
        } else {
          setError(err.message || "Failed to load PR details");
        }
      })
      .finally(() => setLoading(false));
  }, [owner, repo, prNumber]);

  const handleRunAnalysis = async () => {
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const res = await api.analyzePRContribution(owner, repo, prNumber);
      setDetail((prev) => (prev ? { ...prev, reflection: res.reflection } : prev));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Analysis request failed";
      setAnalysisError(message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleToggleBookmark = async () => {
    if (!detail) return;
    const nextSaved = !isSaved;
    try {
      await api.saveContributionBookmark(
        `${owner}/${repo}`,
        prNumber,
        nextSaved,
        detail.pr.title,
        detail.pr.user?.login || "unknown",
        detail.pr.html_url
      );
      setIsSaved(nextSaved);
    } catch {
      // ignore
    }
  };

  const toggleFilePatch = (filename: string) => {
    setExpandedFiles((prev) => ({
      ...prev,
      [filename]: !prev[filename],
    }));
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-44 bg-slate-200 rounded-xl" />
        <div className="h-96 bg-slate-100 rounded-xl" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <EmptyState
        title="Contribution Not Found"
        description={error || `Could not find PR #${prNumber} in ${owner}/${repo}.`}
        icon={AlertCircle}
        actionText="Back to Contributions"
        onAction={() => router.push("/contributions")}
      />
    );
  }

  const { pr, files, total_patch_char_count, reflection } = detail;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <Link
                href={`/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`}
                className="text-xs font-bold text-indigo-600 hover:underline flex items-center gap-1"
              >
                <FolderGit2 className="w-3.5 h-3.5" />
                {owner}/{repo}
              </Link>
              <span className="text-slate-300">•</span>
              <span className="text-xs font-mono text-slate-500 font-semibold">#{pr.number}</span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                  pr.merged_at
                    ? "bg-purple-100 text-purple-800 border border-purple-200"
                    : pr.state === "open"
                    ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                    : "bg-slate-100 text-slate-600 border border-slate-200"
                }`}
              >
                {pr.merged_at ? "merged" : pr.state}
              </span>
            </div>

            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              {pr.title}
            </h1>

            <div className="flex items-center gap-4 text-xs text-slate-500 pt-1">
              {pr.user && (
                <Link
                  href={`/profiles/${pr.user.login}`}
                  className="flex items-center gap-1.5 font-medium text-slate-700 hover:text-indigo-600"
                >
                  {pr.user.avatar_url && (
                    <img
                      src={pr.user.avatar_url}
                      alt={pr.user.login}
                      className="w-4 h-4 rounded-full"
                    />
                  )}
                  <span>@{pr.user.login}</span>
                </Link>
              )}
              <span>
                Created{" "}
                {new Date(pr.created_at).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </span>
              {pr.merged_at && (
                <span className="text-purple-600 font-medium">
                  Merged{" "}
                  {new Date(pr.merged_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              )}
            </div>
          </div>

          {/* Action Header Buttons */}
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              onClick={handleToggleBookmark}
              className={`p-2.5 rounded-lg border transition-colors cursor-pointer flex items-center gap-1.5 text-xs font-semibold ${
                isSaved
                  ? "bg-amber-50 text-amber-700 border-amber-300"
                  : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
              }`}
            >
              {isSaved ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
              <span>{isSaved ? "Saved" : "Save"}</span>
            </button>

            {pr.user && (
              <Link
                href={`/outreach?username=${encodeURIComponent(pr.user.login)}&repo=${encodeURIComponent(
                  `${owner}/${repo}`
                )}&pr=${pr.number}&title=${encodeURIComponent(pr.title)}`}
                className="px-3.5 py-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <Mail className="w-4 h-4" />
                <span>Outreach to Contributor</span>
              </Link>
            )}

            <a
              href={pr.html_url}
              target="_blank"
              rel="noreferrer"
              className="px-3.5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>GitHub PR</span>
            </a>
          </div>
        </div>
      </div>

      {/* Main Grid: AI Learnings (Left) & Changed Files / Diff (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Left Column: Gemini AI Analysis Panel */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <span className="p-1.5 bg-indigo-50 text-indigo-600 rounded-lg">
                <Sparkles className="w-5 h-5" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Gemini AI Technical Reflection</h3>
                <p className="text-[11px] text-slate-500">
                  Grounded engineering post-mortem using LangChain LCEL
                </p>
              </div>
            </div>

            <button
              onClick={handleRunAnalysis}
              disabled={analyzing}
              className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <RotateCw className={`w-3.5 h-3.5 ${analyzing ? "animate-spin" : ""}`} />
              <span>{analyzing ? "Analyzing..." : reflection ? "Re-Analyze" : "Analyze with Gemini"}</span>
            </button>
          </div>

          {analysisError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
              <span>{analysisError}</span>
            </div>
          )}

          {!reflection && !analyzing ? (
            <div className="py-12 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-indigo-50 text-indigo-500 flex items-center justify-center mx-auto">
                <Sparkles className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-semibold text-slate-900">No Reflection Generated Yet</h4>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Generate an evidence-grounded technical post-mortem including Issue Details, Execution Summary,
                and concrete Key Learnings.
              </p>
              <button
                onClick={handleRunAnalysis}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
              >
                Generate Reflection Now
              </button>
            </div>
          ) : analyzing ? (
            <div className="py-16 text-center space-y-3">
              <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-xs text-slate-600 font-medium">
                Gemini is analyzing changed files, diffs, and problem statements...
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* 1. Issue Details */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-900 tracking-wider uppercase flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  Issue Details & Problem Statement
                </h4>
                <div className="p-4 bg-slate-50 border border-slate-200/60 rounded-lg text-xs text-slate-700 leading-relaxed whitespace-pre-line font-sans">
                  {reflection?.issue_details}
                </div>
              </div>

              {/* 2. Execution Summary */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-900 tracking-wider uppercase flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  Execution Summary
                </h4>
                <div className="p-4 bg-slate-50 border border-slate-200/60 rounded-lg text-xs text-slate-700 leading-relaxed whitespace-pre-line font-sans">
                  {reflection?.execution_summary}
                </div>
              </div>

              {/* 3. Key Learnings */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-900 tracking-wider uppercase flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  Key Learnings ({reflection?.key_learnings.length})
                </h4>
                <div className="space-y-2.5">
                  {reflection?.key_learnings.map((learning, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 bg-emerald-50/40 border border-emerald-200/70 rounded-lg text-xs text-slate-800 leading-relaxed"
                    >
                      <div className="flex items-start gap-2">
                        <span className="font-bold text-emerald-700 font-mono text-[11px] shrink-0 mt-0.5">
                          #{idx + 1}
                        </span>
                        <span>{learning}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Code Changes, Files, and Patch Snippets */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-slate-600" />
              <h3 className="text-sm font-bold text-slate-900">Changed Files ({files.length})</h3>
            </div>
            <span className="text-[11px] text-slate-400 font-mono">
              {total_patch_char_count.toLocaleString()} diff chars
            </span>
          </div>

          {files.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-400">
              No changed files recorded for this pull request.
            </div>
          ) : (
            <div className="divide-y divide-slate-100 max-h-[700px] overflow-y-auto pr-1">
              {files.map((file) => {
                const isExpanded = expandedFiles[file.filename] ?? false;

                return (
                  <div key={file.filename} className="py-3 space-y-2">
                    <div
                      onClick={() => toggleFilePatch(file.filename)}
                      className="flex items-center justify-between cursor-pointer hover:bg-slate-50 p-2 rounded-md transition-colors"
                    >
                      <div className="min-w-0 pr-2">
                        <p className="text-xs font-mono font-semibold text-slate-800 truncate">
                          {file.filename}
                        </p>
                        <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-0.5">
                          <span className="text-emerald-600 font-mono">+{file.additions}</span>
                          <span className="text-rose-600 font-mono">-{file.deletions}</span>
                          <span className="capitalize text-slate-500 font-sans">({file.status})</span>
                        </div>
                      </div>

                      <div className="text-slate-400 hover:text-slate-600 p-1">
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </div>
                    </div>

                    {/* Diff Patch Viewer */}
                    {isExpanded && (
                      <div className="mt-2 rounded-lg bg-slate-900 p-3 overflow-x-auto text-[11px] font-mono leading-relaxed text-slate-200">
                        {file.patch ? (
                          <pre className="whitespace-pre">
                            {file.patch.split("\n").map((line, idx) => {
                              const isAdded = line.startsWith("+");
                              const isRemoved = line.startsWith("-");
                              const isHunk = line.startsWith("@@");

                              let lineClass = "text-slate-300";
                              if (isAdded) lineClass = "text-emerald-400 bg-emerald-950/40";
                              if (isRemoved) lineClass = "text-rose-400 bg-rose-950/40";
                              if (isHunk) lineClass = "text-indigo-400 font-semibold";

                              return (
                                <div key={idx} className={`px-1 rounded-xs ${lineClass}`}>
                                  {line}
                                </div>
                              );
                            })}
                          </pre>
                        ) : (
                          <div className="text-slate-400 italic">
                            Binary file or diff omitted by GitHub API.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ContributionDetailPage() {
  return (
    <React.Suspense fallback={<div className="h-48 bg-slate-100 rounded-xl animate-pulse" />}>
      <ContributionDetailPageContent />
    </React.Suspense>
  );
}

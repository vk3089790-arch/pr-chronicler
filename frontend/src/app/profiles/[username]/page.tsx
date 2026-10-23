"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  User,
  GitPullRequest,
  FolderGit2,
  MapPin,
  Building,
  Link as LinkIcon,
  AtSign,
  Mail,
  ExternalLink,
  AlertCircle,
  Sparkles,
  Filter,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { ContributorProfile, ExplorerPRItem, RepositoryMetadata } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";

function ContributorProfilePageContent() {
  const params = useParams();
  const router = useRouter();
  const username = decodeURIComponent(String(params.username || ""));

  const [profile, setProfile] = useState<ContributorProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"prs" | "repos">("prs");

  // Pull Requests State
  const [prs, setPrs] = useState<ExplorerPRItem[]>([]);
  const [prsTotal, setPrsTotal] = useState(0);
  const [prsLoading, setPrsLoading] = useState(true);
  const [prStateFilter, setPrStateFilter] = useState<"all" | "merged" | "open" | "closed">("all");
  const [prPage, setPrPage] = useState(1);

  // Repositories State
  const [repos, setRepos] = useState<RepositoryMetadata[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [repoSort, setRepoSort] = useState("updated");

  // Fetch Profile
  useEffect(() => {
    if (!username) return;
    setProfileLoading(true);
    setProfileError(null);

    api.getUserProfile(username)
      .then((data) => {
        setProfile(data);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setProfileError(`GitHub user '@${username}' was not found. Please verify the username.`);
        } else {
          setProfileError(err.message || "Failed to load user profile");
        }
      })
      .finally(() => setProfileLoading(false));
  }, [username]);

  // Fetch PRs
  const fetchPRs = useCallback(() => {
    if (!username) return;
    setPrsLoading(true);
    api.getUserPullRequests(username, prStateFilter, prPage, 20)
      .then((data) => {
        setPrs(data.items);
        setPrsTotal(data.total_count);
      })
      .catch(() => {
        setPrs([]);
        setPrsTotal(0);
      })
      .finally(() => setPrsLoading(false));
  }, [username, prStateFilter, prPage]);

  useEffect(() => {
    if (activeTab === "prs") {
      fetchPRs();
    }
  }, [activeTab, fetchPRs]);

  // Fetch Repos
  useEffect(() => {
    if (activeTab === "repos" && username) {
      setReposLoading(true);
      api.getUserRepositories(username, repoSort, 1, 30)
        .then((data) => setRepos(data))
        .catch(() => setRepos([]))
        .finally(() => setReposLoading(false));
    }
  }, [activeTab, username, repoSort]);

  if (profileLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-48 bg-slate-200 rounded-xl" />
        <div className="h-64 bg-slate-100 rounded-xl" />
      </div>
    );
  }

  if (profileError || !profile) {
    return (
      <EmptyState
        title="Contributor Not Found"
        description={profileError || `Unable to locate GitHub user @${username}.`}
        icon={AlertCircle}
        actionText="Search Another Contributor"
        onAction={() => router.push("/profiles")}
      />
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Profile Header Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-start sm:items-center gap-5">
            {profile.avatar_url ? (
              <img
                src={profile.avatar_url}
                alt={profile.login}
                className="w-20 h-20 rounded-full border-2 border-indigo-500/30 object-cover shadow-sm shrink-0"
              />
            ) : (
              <div className="w-20 h-20 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
                <User className="w-10 h-10" />
              </div>
            )}

            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                  {profile.name || profile.login}
                </h2>
                <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">
                  @{profile.login}
                </span>
              </div>

              {profile.bio && (
                <p className="text-xs text-slate-600 max-w-xl leading-relaxed">{profile.bio}</p>
              )}

              {/* Badges / Metadata */}
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
                {profile.company && (
                  <span className="flex items-center gap-1">
                    <Building className="w-3.5 h-3.5 text-slate-400" />
                    {profile.company}
                  </span>
                )}
                {profile.location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    {profile.location}
                  </span>
                )}
                {profile.blog && (
                  <a
                    href={profile.blog.startsWith("http") ? profile.blog : `https://${profile.blog}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-indigo-600 hover:underline"
                  >
                    <LinkIcon className="w-3.5 h-3.5" />
                    Website
                  </a>
                )}
                {profile.twitter_username && (
                  <a
                    href={`https://twitter.com/${profile.twitter_username}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-sky-500 hover:underline"
                  >
                    <AtSign className="w-3.5 h-3.5" />
                    @{profile.twitter_username}
                  </a>
                )}
              </div>
            </div>
          </div>

          {/* Action Buttons: Outreach & GitHub */}
          <div className="flex flex-wrap sm:flex-col items-end gap-2 shrink-0 w-full sm:w-auto">
            <Link
              href={`/outreach?username=${encodeURIComponent(profile.login)}${
                profile.email ? `&email=${encodeURIComponent(profile.email)}` : ""
              }`}
              className="w-full sm:w-auto px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs flex items-center justify-center gap-2 transition-colors cursor-pointer"
            >
              <Mail className="w-4 h-4" />
              Compose Outreach
            </Link>

            <a
              href={profile.html_url}
              target="_blank"
              rel="noreferrer"
              className="w-full sm:w-auto px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5 text-slate-500" />
              View on GitHub
            </a>
          </div>
        </div>

        {/* Contributor Metrics Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-slate-100">
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-[11px] font-medium text-slate-500">Public Repos</span>
            <p className="text-lg font-bold text-slate-900 mt-0.5">{profile.public_repos}</p>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-[11px] font-medium text-slate-500">Followers</span>
            <p className="text-lg font-bold text-slate-900 mt-0.5">{profile.followers.toLocaleString()}</p>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-[11px] font-medium text-slate-500">Following</span>
            <p className="text-lg font-bold text-slate-900 mt-0.5">{profile.following.toLocaleString()}</p>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <span className="text-[11px] font-medium text-slate-500">Public Email</span>
            <p className="text-xs font-semibold text-slate-800 mt-1 truncate">
              {profile.email ? (
                <span className="text-emerald-700 flex items-center gap-1 font-mono">
                  {profile.email}
                </span>
              ) : (
                <span className="text-slate-400 italic">Not listed on GitHub</span>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Tabs Row */}
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
          Authored Pull Requests
          {prsTotal > 0 && (
            <span className="px-2 py-0.5 text-xs bg-slate-100 text-slate-700 rounded-full font-mono">
              {prsTotal}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("repos")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeTab === "repos"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <FolderGit2 className="w-4 h-4" />
          Public Repositories
          <span className="px-2 py-0.5 text-xs bg-slate-100 text-slate-700 rounded-full font-mono">
            {profile.public_repos}
          </span>
        </button>
      </div>

      {/* Tab Content: Pull Requests */}
      {activeTab === "prs" && (
        <div className="space-y-4">
          {/* PR Filter Controls */}
          <div className="flex items-center justify-between flex-wrap gap-3 bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-400" />
              <span className="text-xs font-semibold text-slate-700">Filter Status:</span>
              <div className="flex gap-1">
                {(["all", "merged", "open", "closed"] as const).map((s) => (
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
              Showing {prs.length} of {prsTotal} pull requests
            </span>
          </div>

          {/* PRs List */}
          {prsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : prs.length === 0 ? (
            <div className="bg-white p-8 rounded-xl border border-slate-200 text-center text-xs text-slate-500">
              No pull requests found matching the state filter &quot;{prStateFilter}&quot;.
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200/80 divide-y divide-slate-100 shadow-xs overflow-hidden">
              {prs.map((pr) => {
                const repoParts = (pr.repo_full_name || "").split("/");
                const owner = repoParts[0] || "";
                const repo = repoParts[1] || "";

                return (
                  <div
                    key={pr.number + (pr.html_url || "")}
                    className="p-5 hover:bg-slate-50/80 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="min-w-0 space-y-1.5 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-slate-900">
                          {pr.repo_full_name || "Repository"}
                        </span>
                        <span className="text-xs font-mono text-indigo-600">#{pr.number}</span>
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

                      <h4 className="text-sm font-semibold text-slate-800 leading-snug">
                        {pr.title}
                      </h4>

                      <div className="flex items-center gap-4 text-[11px] text-slate-400">
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

                    <div className="flex items-center gap-2 shrink-0">
                      {owner && repo ? (
                        <Link
                          href={`/contributions/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${pr.number}`}
                          className="px-3.5 py-2 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg shadow-xs transition-colors flex items-center gap-1.5"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          Inspect & Analyze
                        </Link>
                      ) : (
                        <a
                          href={pr.html_url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-3.5 py-2 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors flex items-center gap-1.5"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          View on GitHub
                        </a>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab Content: Repositories */}
      {activeTab === "repos" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs">
            <span className="text-xs font-semibold text-slate-700">Sort Repositories:</span>
            <select
              value={repoSort}
              onChange={(e) => setRepoSort(e.target.value)}
              className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none"
            >
              <option value="updated">Recently Updated</option>
              <option value="stars">Most Stars</option>
              <option value="pushed">Recently Pushed</option>
              <option value="full_name">Alphabetical</option>
            </select>
          </div>

          {reposLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-32 bg-slate-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : repos.length === 0 ? (
            <div className="bg-white p-8 rounded-xl border border-slate-200 text-center text-xs text-slate-500">
              No public repositories found.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {repos.map((repo) => {
                const [owner, name] = (repo.full_name || "").split("/");
                return (
                  <div
                    key={repo.full_name}
                    className="p-5 bg-white rounded-xl border border-slate-200/80 hover:border-indigo-300 hover:shadow-xs transition-all flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <Link
                          href={`/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`}
                          className="text-sm font-bold text-slate-900 hover:text-indigo-600 transition-colors truncate"
                        >
                          {repo.name}
                        </Link>
                        <span className="text-xs text-slate-500 font-mono">
                          ★ {repo.stargazers_count}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 mt-2 line-clamp-2">
                        {repo.description || "No description provided."}
                      </p>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                      {repo.language ? (
                        <span className="flex items-center gap-1.5 font-medium">
                          <span className="w-2 h-2 rounded-full bg-indigo-500" />
                          {repo.language}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic">No primary language</span>
                      )}
                      <Link
                        href={`/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`}
                        className="text-indigo-600 hover:text-indigo-700 font-semibold flex items-center gap-1 text-[11px]"
                      >
                        Explore Repo &rarr;
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ContributorProfilePage() {
  return (
    <React.Suspense fallback={<div className="h-48 bg-slate-100 rounded-xl animate-pulse" />}>
      <ContributorProfilePageContent />
    </React.Suspense>
  );
}

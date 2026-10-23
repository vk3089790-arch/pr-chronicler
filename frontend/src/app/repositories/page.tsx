"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { FolderGit2, Search, ArrowRight, Clock } from "lucide-react";
import { api } from "@/lib/api";
import { RecentSearchItem } from "@/lib/types";

const FEATURED_REPOSITORIES = [
  {
    owner: "fastapi",
    repo: "fastapi",
    description: "FastAPI framework, high performance, easy to learn, fast to code, ready for production",
    language: "Python",
  },
  {
    owner: "pallets",
    repo: "flask",
    description: "The Python micro framework for building web applications.",
    language: "Python",
  },
  {
    owner: "langchain-ai",
    repo: "langchain",
    description: "Build context-aware reasoning applications with LangChain.",
    language: "Python",
  },
  {
    owner: "facebook",
    repo: "react",
    description: "The library for web and native user interfaces.",
    language: "JavaScript",
  },
  {
    owner: "vercel",
    repo: "next.js",
    description: "The React Framework for the Web.",
    language: "TypeScript",
  },
];

export default function RepositoriesIndexPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [recentSearches, setRecentSearches] = useState<RecentSearchItem[]>([]);

  useEffect(() => {
    api.getRecentSearches(20)
      .then((items) => setRecentSearches(items.filter((i) => i.search_type === "repo")))
      .catch(() => {});
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = query
      .trim()
      .replace(/^https?:\/\/github\.com\//, "")
      .replace(/\/+$/, "");
    if (clean.includes("/")) {
      const [owner, repo] = clean.split("/");
      router.push(`/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`);
    } else {
      // If single term, search via explorer
      api.searchExplorer(clean, "repo").then((res) => {
        router.push(`/repositories/${encodeURIComponent(res.identifier1)}/${encodeURIComponent(res.identifier2 || "")}`);
      }).catch(() => {});
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Search Header */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 mb-2 text-indigo-600">
            <FolderGit2 className="w-5 h-5" />
            <h2 className="text-xl font-bold tracking-tight text-slate-900">Repository Explorer</h2>
          </div>
          <p className="text-sm text-slate-600">
            Inspect repository pull requests, technical changes, top contributors,
            and extract AI engineering takeaways.
          </p>

          <form onSubmit={handleSearch} className="mt-4 flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter repository as 'owner/repo' or GitHub repo URL..."
                className="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              disabled={!query.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              Explore
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      </div>

      {/* Featured Repositories */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
        <h3 className="text-sm font-semibold text-slate-900 mb-4">Featured Open-Source Repositories</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURED_REPOSITORIES.map((r) => (
            <Link
              key={`${r.owner}/${r.repo}`}
              href={`/repositories/${r.owner}/${r.repo}`}
              className="p-4 rounded-lg bg-slate-50 border border-slate-200/60 hover:border-indigo-400 hover:bg-indigo-50/30 transition-all flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900 group-hover:text-indigo-600">
                    {r.owner}/{r.repo}
                  </span>
                  <span className="text-[10px] font-medium text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                    {r.language}
                  </span>
                </div>
                <p className="text-xs text-slate-600 mt-2 line-clamp-2">{r.description}</p>
              </div>

              <div className="mt-4 pt-2 border-t border-slate-200/50 flex items-center justify-between text-xs text-indigo-600 font-semibold">
                <span>View PRs & Contributors</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Recently Explored Repositories */}
      {recentSearches.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">Recently Explored Repositories</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {recentSearches.map((item) => {
              const [owner, repo] = item.target.split("/");
              return (
                <Link
                  key={item.id}
                  href={`/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`}
                  className="px-3 py-1.5 bg-slate-100 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 rounded-lg text-xs font-medium border border-slate-200/60 transition-colors flex items-center gap-1.5"
                >
                  <FolderGit2 className="w-3.5 h-3.5" />
                  {item.target}
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

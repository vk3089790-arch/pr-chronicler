"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { User, Search, ArrowRight, Clock } from "lucide-react";
import { api } from "@/lib/api";
import { RecentSearchItem } from "@/lib/types";

const POPULAR_CONTRIBUTORS = [
  { username: "tiangolo", name: "Sebastián Ramírez", role: "Creator of FastAPI & Typer" },
  { username: "torvalds", name: "Linus Torvalds", role: "Creator of Linux & Git" },
  { username: "mitsuhiko", name: "Armin Ronacher", role: "Creator of Flask & Jinja" },
  { username: "kennethreitz", name: "Kenneth Reitz", role: "Creator of Requests" },
  { username: "antirez", name: "Salvatore Sanfilippo", role: "Creator of Redis" },
];

export default function ProfilesIndexPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [recentSearches, setRecentSearches] = useState<RecentSearchItem[]>([]);

  useEffect(() => {
    api.getRecentSearches(20)
      .then((items) => setRecentSearches(items.filter((i) => i.search_type === "user")))
      .catch(() => {});
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = query.trim().replace(/^https?:\/\/github\.com\//, "").replace(/^@/, "");
    if (clean) {
      router.push(`/profiles/${encodeURIComponent(clean)}`);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 mb-2 text-indigo-600">
            <User className="w-5 h-5" />
            <h2 className="text-xl font-bold tracking-tight text-slate-900">Contributor Profiles</h2>
          </div>
          <p className="text-sm text-slate-600">
            Explore public open-source contributions, authored pull requests, and activity
            profiles across the global developer community.
          </p>

          <form onSubmit={handleSearch} className="mt-4 flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter GitHub username or profile URL..."
                className="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              disabled={!query.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              Search
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      </div>

      {/* Suggested & Popular Contributors */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
        <h3 className="text-sm font-semibold text-slate-900 mb-4">Notable Open-Source Leaders</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {POPULAR_CONTRIBUTORS.map((c) => (
            <Link
              key={c.username}
              href={`/profiles/${c.username}`}
              className="p-4 rounded-lg bg-slate-50 border border-slate-200/60 hover:border-indigo-400 hover:bg-indigo-50/30 transition-all flex items-start justify-between group"
            >
              <div>
                <p className="text-xs font-bold text-slate-900 group-hover:text-indigo-600">
                  {c.name}
                </p>
                <p className="text-xs text-indigo-600 font-mono">@{c.username}</p>
                <p className="text-[11px] text-slate-500 mt-1">{c.role}</p>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-600 transition-colors" />
            </Link>
          ))}
        </div>
      </div>

      {/* Recently Viewed Profiles */}
      {recentSearches.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200/80 p-6 shadow-xs">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">Recently Explored Contributors</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {recentSearches.map((item) => (
              <Link
                key={item.id}
                href={`/profiles/${item.target}`}
                className="px-3 py-1.5 bg-slate-100 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 rounded-lg text-xs font-medium border border-slate-200/60 transition-colors flex items-center gap-1.5"
              >
                <User className="w-3.5 h-3.5" />
                @{item.target}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

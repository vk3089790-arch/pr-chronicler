"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Compass,
  Users,
  FolderGit2,
  GitPullRequest,
  Sparkles,
  Mail,
  Webhook,
  Activity,
  Settings,
  GitMerge,
  ExternalLink,
} from "lucide-react";

const NAV_ITEMS = [
  { name: "Explore", href: "/", icon: Compass },
  { name: "Profiles", href: "/profiles", icon: Users },
  { name: "Repositories", href: "/repositories", icon: FolderGit2 },
  { name: "Contributions", href: "/contributions", icon: GitPullRequest },
  { name: "AI Learnings", href: "/learnings", icon: Sparkles },
  { name: "Email Outreach", href: "/outreach", icon: Mail },
  { name: "Webhook Automation", href: "/webhook-automation", icon: Webhook },
  { name: "System Health", href: "/system-health", icon: Activity },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col shrink-0 text-slate-300 min-h-screen">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-slate-800 gap-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-indigo-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
          <GitMerge className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-semibold text-white tracking-tight text-sm">PR Chronicler</h1>
          <p className="text-[11px] text-slate-400 font-mono">v1.0.0 • SQLite WAL</p>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <div className="px-3 pb-2 text-[10px] font-semibold tracking-wider text-slate-500 uppercase">
          Menu
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-indigo-600 text-white shadow-xs font-semibold"
                  : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "text-white" : "text-slate-400"}`} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Secondary / External documentation link */}
      <div className="p-4 border-t border-slate-800">
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-between px-3 py-2 text-xs font-medium text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60 transition-colors"
        >
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            FastAPI Docs
          </span>
          <ExternalLink className="w-3.5 h-3.5 text-slate-500" />
        </a>
        <div className="mt-3 px-3 py-2 rounded-lg bg-slate-800/40 border border-slate-800 text-[11px] text-slate-400">
          Backend API active on <span className="font-mono text-slate-300">port 8000</span>
        </div>
      </div>
    </aside>
  );
}

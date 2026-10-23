import React from "react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  variant?: "default" | "success" | "warning" | "danger" | "info";
  isLoading?: boolean;
}

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = "default",
  isLoading = false,
}: StatCardProps) {
  const iconColors = {
    default: "bg-slate-100 text-slate-700",
    success: "bg-emerald-50 text-emerald-600 border border-emerald-100",
    warning: "bg-amber-50 text-amber-600 border border-amber-100",
    danger: "bg-rose-50 text-rose-600 border border-rose-100",
    info: "bg-indigo-50 text-indigo-600 border border-indigo-100",
  }[variant];

  return (
    <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs hover:border-slate-300 transition-all">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {title}
        </span>
        <div className={`p-2.5 rounded-lg ${iconColors}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="mt-4">
        {isLoading ? (
          <div className="h-8 w-20 bg-slate-100 rounded animate-pulse" />
        ) : (
          <div className="text-2xl font-bold text-slate-900 tracking-tight">
            {value}
          </div>
        )}
        {subtitle && (
          <p className="mt-1 text-xs text-slate-500 line-clamp-1">{subtitle}</p>
        )}
      </div>
    </div>
  );
}

import React from "react";

export function TableSkeleton({ rows = 5, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="w-full bg-white rounded-xl border border-slate-200/80 overflow-hidden divide-y divide-slate-100">
      <div className="px-6 py-4 bg-slate-50 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="h-4 bg-slate-200 rounded animate-pulse flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="px-6 py-4 flex gap-4 items-center">
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className={`h-4 bg-slate-100 rounded animate-pulse ${
                c === 0 ? "w-28 shrink-0" : "flex-1"
              }`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
      <div className="flex justify-between items-center">
        <div className="h-4 w-24 bg-slate-100 rounded animate-pulse" />
        <div className="h-8 w-8 bg-slate-100 rounded-lg animate-pulse" />
      </div>
      <div className="mt-4">
        <div className="h-7 w-16 bg-slate-200 rounded animate-pulse" />
        <div className="mt-2 h-3 w-32 bg-slate-100 rounded animate-pulse" />
      </div>
    </div>
  );
}

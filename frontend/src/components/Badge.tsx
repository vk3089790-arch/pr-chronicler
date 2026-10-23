import React from "react";
import { DeliveryStatus, EmailStatus } from "@/lib/types";

interface BadgeProps {
  children?: React.ReactNode;
  variant?: "status" | "email" | "evidence" | "neutral";
  status?: DeliveryStatus | EmailStatus | string;
  size?: "sm" | "md";
  className?: string;
}

export function Badge({
  children,
  variant = "status",
  status,
  size = "md",
  className = "",
}: BadgeProps) {
  const value = (children ? String(children) : status || "").toUpperCase();
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs";

  let colorClasses = "bg-slate-100 text-slate-700 border-slate-200";

  if (variant === "evidence") {
    if (value.includes("VERIFIED")) {
      colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200 font-medium";
    } else if (value.includes("INFERRED")) {
      colorClasses = "bg-indigo-50 text-indigo-700 border-indigo-200 font-medium";
    } else if (value.includes("UNVERIFIED")) {
      colorClasses = "bg-amber-50 text-amber-700 border-amber-200 font-medium";
    }
  } else if (variant === "email") {
    switch (value) {
      case "SENT":
        colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200";
        break;
      case "FAILED":
        colorClasses = "bg-rose-50 text-rose-700 border-rose-200";
        break;
      case "NOT_SENT":
      default:
        colorClasses = "bg-slate-100 text-slate-500 border-slate-200";
        break;
    }
  } else {
    // Delivery status variant
    switch (value) {
      case "COMPLETED":
        colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200";
        break;
      case "PROCESSING":
        colorClasses = "bg-amber-50 text-amber-700 border-amber-200 animate-pulse";
        break;
      case "FAILED":
        colorClasses = "bg-rose-50 text-rose-700 border-rose-200";
        break;
      case "IGNORED":
        colorClasses = "bg-slate-100 text-slate-600 border-slate-200";
        break;
      default:
        colorClasses = "bg-slate-100 text-slate-700 border-slate-200";
        break;
    }
  }

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border shadow-xs tracking-wide transition-colors ${sizeClasses} ${colorClasses} ${className}`}
    >
      {children || status}
    </span>
  );
}

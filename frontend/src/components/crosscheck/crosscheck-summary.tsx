import React from "react";
import { CrossCheckResult } from "@/lib/api/types";
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  FileMinus,
  FilePlus,
  AlertOctagon,
} from "lucide-react";

interface CrossCheckSummaryProps {
  summary: CrossCheckResult["summary"];
  selectedFilter?: string | null;
  onSelectFilter?: (status: string | null) => void;
}

export function CrossCheckSummary({
  summary,
  selectedFilter,
  onSelectFilter,
}: CrossCheckSummaryProps) {
  const stats = [
    {
      key: "MATCHED",
      label: "Matched",
      value: summary.matched,
      icon: <CheckCircle2 className="h-5 w-5 text-emerald-500" />,
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      textColor: "text-emerald-700",
      activeRing: "ring-2 ring-emerald-500 bg-emerald-100/60 shadow-md",
    },
    {
      key: "CHANGED",
      label: "Changed",
      value: summary.changed,
      icon: <AlertTriangle className="h-5 w-5 text-amber-500" />,
      bg: "bg-amber-50",
      border: "border-amber-200",
      textColor: "text-amber-700",
      activeRing: "ring-2 ring-amber-500 bg-amber-100/60 shadow-md",
    },
    {
      key: "MISSING",
      label: "Missing",
      value: summary.missing,
      icon: <FileMinus className="h-5 w-5 text-rose-500" />,
      bg: "bg-rose-50",
      border: "border-rose-200",
      textColor: "text-rose-700",
      activeRing: "ring-2 ring-rose-500 bg-rose-100/60 shadow-md",
    },
    {
      key: "EXTRA",
      label: "Extra",
      value: summary.extra,
      icon: <FilePlus className="h-5 w-5 text-purple-500" />,
      bg: "bg-purple-50",
      border: "border-purple-200",
      textColor: "text-purple-700",
      activeRing: "ring-2 ring-purple-500 bg-purple-100/60 shadow-md",
    },
    {
      key: "UNCERTAIN",
      label: "Uncertain",
      value: summary.uncertain,
      icon: <HelpCircle className="h-5 w-5 text-slate-500" />,
      bg: "bg-slate-50",
      border: "border-slate-200",
      textColor: "text-slate-700",
      activeRing: "ring-2 ring-slate-500 bg-slate-100/60 shadow-md",
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {stats.map((stat) => {
          const isSelected = selectedFilter === stat.key;
          return (
            <button
              key={stat.key}
              type="button"
              onClick={() => {
                if (onSelectFilter) {
                  onSelectFilter(isSelected ? null : stat.key);
                }
              }}
              className={`rounded-xl border ${stat.border} ${stat.bg} p-4 flex flex-col items-center justify-center text-center transition-all cursor-pointer hover:scale-[1.02] hover:shadow-sm focus-visible:outline-none ${
                isSelected ? stat.activeRing : "opacity-90 hover:opacity-100"
              }`}
            >
              <div className="mb-2">{stat.icon}</div>
              <div className={`text-2xl font-bold ${stat.textColor}`}>
                {stat.value}
              </div>
              <div
                className={`text-xs font-semibold uppercase tracking-wider ${stat.textColor} mt-1`}
              >
                {stat.label}
              </div>
              {isSelected && (
                <span className="mt-1 text-[10px] font-bold text-slate-600 bg-white/80 px-2 py-0.5 rounded-full border border-slate-200">
                  Active Filter ✕
                </span>
              )}
            </button>
          );
        })}
      </div>

      {(summary.critical_discrepancies > 0 || summary.open_reviews > 0) && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 p-4 rounded-xl border border-rose-200 bg-rose-50/50">
          <AlertOctagon className="h-5 w-5 text-rose-500 shrink-0" />
          <div className="text-sm text-rose-800 flex-1">
            <span className="font-semibold">Attention Required:</span> There are{" "}
            <span className="font-bold">{summary.critical_discrepancies}</span> critical discrepancies and{" "}
            <span className="font-bold">{summary.open_reviews}</span> open reviews that need your attention.
          </div>
        </div>
      )}
    </div>
  );
}

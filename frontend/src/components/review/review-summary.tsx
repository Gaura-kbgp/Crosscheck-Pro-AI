import React from "react";
import { DiscrepancySummary } from "@/lib/api/types";
import { AlertCircle, FileWarning, ShieldAlert, CheckCircle2, ShieldQuestion, Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReviewSummaryProps {
  /** Backend-computed summary (DiscrepancySummary in app/api/v1/crosscheck.py) —
   * the single source of truth, so open always equals critical + high + warning + info. */
  summary: DiscrepancySummary;
}

export function ReviewSummary({ summary }: ReviewSummaryProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-7 gap-4">
      <StatCard
        label="Open"
        value={summary.open}
        icon={<AlertCircle className="h-4 w-4" />}
        colorClass="text-amber-600 bg-amber-50 border-amber-200"
      />
      <StatCard
        label="Escalated"
        value={summary.escalated}
        icon={<ShieldQuestion className="h-4 w-4" />}
        colorClass="text-rose-600 bg-rose-50 border-rose-200"
      />
      <StatCard
        label="Reviewed"
        value={summary.reviewed}
        icon={<CheckCircle2 className="h-4 w-4" />}
        colorClass="text-emerald-600 bg-emerald-50 border-emerald-200"
      />
      <StatCard
        label="Critical"
        value={summary.critical}
        icon={<ShieldAlert className="h-4 w-4" />}
        colorClass="text-rose-600 bg-rose-50 border-rose-200"
      />
      <StatCard
        label="High"
        value={summary.high}
        icon={<FileWarning className="h-4 w-4" />}
        colorClass="text-orange-600 bg-orange-50 border-orange-200"
      />
      <StatCard
        label="Warning"
        value={summary.warning}
        icon={<AlertCircle className="h-4 w-4" />}
        colorClass="text-yellow-600 bg-yellow-50 border-yellow-200"
      />
      <StatCard
        label="Info"
        value={summary.info}
        icon={<Info className="h-4 w-4" />}
        colorClass="text-sky-600 bg-sky-50 border-sky-200"
      />
    </div>
  );
}

function StatCard({ label, value, icon, colorClass }: { label: string; value: number; icon: React.ReactNode; colorClass: string }) {
  return (
    <div className={cn("rounded-xl border p-3 flex flex-col justify-center items-center shadow-2xs text-center", colorClass)}>
      <div className="flex items-center gap-1.5 mb-1.5 opacity-80">
        {icon}
        <span className="text-[11px] font-bold uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
}

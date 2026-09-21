import React from "react";
import { Discrepancy } from "@/lib/api/types";
import { AlertCircle, FileWarning, ShieldAlert, CheckCircle2, ShieldQuestion } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReviewSummaryProps {
  discrepancies: Discrepancy[];
}

export function ReviewSummary({ discrepancies }: ReviewSummaryProps) {
  const openCount = discrepancies.filter((d) => d.status === "OPEN").length;
  const escalatedCount = discrepancies.filter((d) => d.status === "ESCALATED").length;
  const reviewedCount = discrepancies.filter(
    (d) => d.status === "ACCEPTED" || d.status === "FALSE_POSITIVE" || d.status === "ACKNOWLEDGED"
  ).length;

  const criticalCount = discrepancies.filter((d) => d.severity === "CRITICAL").length;
  const highCount = discrepancies.filter((d) => d.severity === "HIGH").length;
  const warningCount = discrepancies.filter((d) => d.severity === "WARNING").length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
      <StatCard 
        label="Open" 
        value={openCount} 
        icon={<AlertCircle className="h-4 w-4" />}
        colorClass="text-amber-600 bg-amber-50 border-amber-200" 
      />
      <StatCard 
        label="Escalated" 
        value={escalatedCount} 
        icon={<ShieldQuestion className="h-4 w-4" />}
        colorClass="text-rose-600 bg-rose-50 border-rose-200" 
      />
      <StatCard 
        label="Reviewed" 
        value={reviewedCount} 
        icon={<CheckCircle2 className="h-4 w-4" />}
        colorClass="text-emerald-600 bg-emerald-50 border-emerald-200" 
      />
      <StatCard 
        label="Critical" 
        value={criticalCount} 
        icon={<ShieldAlert className="h-4 w-4" />}
        colorClass="text-rose-600 bg-rose-50 border-rose-200" 
      />
      <StatCard 
        label="High" 
        value={highCount} 
        icon={<FileWarning className="h-4 w-4" />}
        colorClass="text-orange-600 bg-orange-50 border-orange-200" 
      />
      <StatCard 
        label="Warning" 
        value={warningCount} 
        icon={<AlertCircle className="h-4 w-4" />}
        colorClass="text-yellow-600 bg-yellow-50 border-yellow-200" 
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

import React from "react";
import { Discrepancy, MatchGroup } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { ChevronRight, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDisplayValue } from "@/lib/utils/formatters";

type DiscrepancyWithGroup = Discrepancy & { group: MatchGroup };

interface ReviewListProps {
  discrepancies: DiscrepancyWithGroup[];
  onSelect: (id: string) => void;
}

export function ReviewList({ discrepancies, onSelect }: ReviewListProps) {
  if (discrepancies.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-[#DCE6F0] bg-white p-12 text-center shadow-2xs">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#F7F9FC] text-[#58708F] mb-4 border border-[#DCE6F0]">
          <CheckCircle2 className="h-6 w-6 text-[#16A34A]" />
        </div>
        <h3 className="text-sm font-semibold text-[#0F2747] mb-1">All caught up!</h3>
        <p className="text-xs text-[#58708F] max-w-sm mx-auto">
          No discrepancies match the current filters, or all discrepancies have been reviewed.
        </p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-[#DCE6F0]">
      {discrepancies.map((d) => (
        <ReviewListItem key={d.id} discrepancy={d} onClick={() => onSelect(d.id)} />
      ))}
    </div>
  );
}

function ReviewListItem({ discrepancy, onClick }: { discrepancy: DiscrepancyWithGroup; onClick: () => void }) {
  const getSeverityColor = (sev: string) => {
    switch (sev) {
      case "CRITICAL": return "bg-rose-100 text-rose-700";
      case "HIGH": return "bg-orange-100 text-orange-700";
      case "WARNING": return "bg-yellow-100 text-yellow-700";
      default: return "bg-blue-100 text-blue-700";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "OPEN": return "bg-amber-100 text-amber-700";
      case "ESCALATED": return "bg-rose-100 text-rose-700";
      case "ACCEPTED":
      case "FALSE_POSITIVE":
      case "ACKNOWLEDGED":
        return "bg-emerald-100 text-emerald-700";
      default: return "bg-slate-100 text-slate-700";
    }
  };

  return (
    <div
      onClick={onClick}
      className={cn(
        "group flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 transition-colors hover:bg-sky-50 cursor-pointer",
        discrepancy.severity === "CRITICAL" && discrepancy.status === "OPEN" ? "bg-rose-50/30" : "bg-white"
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <Badge className={cn("px-2 py-0 text-[10px] uppercase tracking-wider font-bold shadow-none border-none", getSeverityColor(discrepancy.severity))}>
            {discrepancy.severity}
          </Badge>
          <Badge className={cn("px-2 py-0 text-[10px] uppercase tracking-wider font-bold shadow-none border-none", getStatusColor(discrepancy.status))}>
            {discrepancy.status}
          </Badge>
          {discrepancy.introduced_at && (
            <span className="text-[10px] text-[#58708F] bg-slate-100 px-1.5 py-0.5 rounded font-medium">
              Introduced: {discrepancy.introduced_at}
            </span>
          )}
        </div>
        
        <div className="flex items-center gap-3">
          <h3 className="text-base font-bold text-[#0F2747] font-mono tracking-tight truncate">
            {discrepancy.group.canonical_sku}
          </h3>
          <span className="text-[#DCE6F0]">|</span>
          <span className="text-sm font-semibold text-[#0F2747]">
            {discrepancy.field_name}
          </span>
        </div>
        
        <div className="mt-1 flex items-center gap-2 text-xs text-[#58708F] truncate">
          <span>Design: <span className="font-mono font-medium text-[#0F2747]">{formatDisplayValue(discrepancy.design_value)}</span></span>
          <ChevronRight className="h-3 w-3 text-slate-300" />
          <span>Order: <span className="font-mono font-medium text-[#0F2747]">{formatDisplayValue(discrepancy.order_value)}</span></span>
          <ChevronRight className="h-3 w-3 text-slate-300" />
          <span>Ack: <span className="font-mono font-medium text-[#0F2747]">{formatDisplayValue(discrepancy.ack_value)}</span></span>
        </div>
      </div>

      <div className="shrink-0 flex items-center justify-end">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-50 text-slate-400 group-hover:bg-[#0EA5E9]/10 group-hover:text-[#0EA5E9] transition-colors">
          <ChevronRight className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

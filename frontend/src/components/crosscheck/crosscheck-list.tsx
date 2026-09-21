import React from "react";
import { MatchGroup } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { ChevronRight, AlertCircle, Filter, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDisplayValue } from "@/lib/utils/formatters";

interface CrossCheckListProps {
  groups: MatchGroup[];
  filterStatus?: string | null;
  onSelectGroup: (id: string) => void;
  onClearFilter?: () => void;
}

export function CrossCheckList({
  groups,
  filterStatus,
  onSelectGroup,
  onClearFilter,
}: CrossCheckListProps) {
  const filteredGroups = filterStatus
    ? groups.filter((g) => g.status.toUpperCase() === filterStatus.toUpperCase())
    : groups;

  if (groups.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-[#DCE6F0] bg-white p-12 text-center shadow-2xs">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#F7F9FC] text-[#58708F] mb-4 border border-[#DCE6F0]">
          <AlertCircle className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-[#0F2747] mb-1">No cross-check results available</h3>
        <p className="text-xs text-[#58708F] max-w-sm mx-auto">
          It looks like this project hasn&apos;t been cross-checked yet, or no items were found.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {filterStatus && (
        <div className="flex items-center justify-between bg-slate-50 px-4 py-2.5 rounded-xl border border-slate-200 text-xs">
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-[#0EA5E9]" />
            <span className="text-[#58708F]">Filtering by status:</span>
            <span className="font-bold text-[#0F2747] uppercase bg-white px-2 py-0.5 rounded border shadow-2xs">
              {filterStatus} ({filteredGroups.length} items)
            </span>
          </div>
          {onClearFilter && (
            <button
              type="button"
              onClick={onClearFilter}
              className="inline-flex items-center gap-1 font-semibold text-[#0EA5E9] hover:text-[#0284C7] cursor-pointer"
            >
              <X className="h-3.5 w-3.5" />
              <span>Show All ({groups.length})</span>
            </button>
          )}
        </div>
      )}

      {filteredGroups.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[#DCE6F0] bg-white p-8 text-center">
          <p className="text-sm font-medium text-[#58708F]">
            No items with status <span className="font-bold text-[#0F2747]">{filterStatus}</span> found.
          </p>
          {onClearFilter && (
            <button
              type="button"
              onClick={onClearFilter}
              className="mt-2 text-xs font-bold text-[#0EA5E9] hover:underline"
            >
              Clear filter
            </button>
          )}
        </div>
      ) : (
        filteredGroups.map((group) => (
          <MatchGroupCard
            key={group.id}
            group={group}
            onClick={() => onSelectGroup(group.id)}
          />
        ))
      )}
    </div>
  );
}

function MatchGroupCard({ group, onClick }: { group: MatchGroup; onClick: () => void }) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case "MATCHED":
        return "bg-emerald-100 text-emerald-700 hover:bg-emerald-200";
      case "CHANGED":
        return "bg-amber-100 text-amber-700 hover:bg-amber-200";
      case "MISSING":
        return "bg-rose-100 text-rose-700 hover:bg-rose-200";
      case "EXTRA":
        return "bg-purple-100 text-purple-700 hover:bg-purple-200";
      default:
        return "bg-slate-100 text-slate-700 hover:bg-slate-200";
    }
  };

  const hasCritical = group.discrepancies.some((d) => d.severity === "CRITICAL");
  const openIssues = group.discrepancies.filter(
    (d) => d.status === "OPEN" || d.status === "ESCALATED"
  ).length;

  const formattedDim = formatDisplayValue(group.final_dimensions);
  const formattedFin = formatDisplayValue(group.final_finish);

  return (
    <div
      onClick={onClick}
      className={cn(
        "group relative flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-[#DCE6F0] bg-white p-4 shadow-2xs transition-all hover:border-[#0EA5E9] hover:shadow-md cursor-pointer",
        hasCritical && "border-rose-200 bg-rose-50/10"
      )}
    >
      <div className="flex items-center gap-4">
        {/* Status Indicator */}
        <div className="flex shrink-0 items-center justify-center">
          <Badge className={cn("px-2.5 py-1 text-xs font-bold shadow-none border-none", getStatusColor(group.status))}>
            {group.status}
          </Badge>
        </div>

        {/* Main Info */}
        <div>
          <h3 className="text-base font-bold text-[#0F2747] font-mono tracking-tight">
            {group.canonical_sku || "Unknown SKU"}
          </h3>
          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-[#58708F]">
            {group.final_quantity !== undefined && group.final_quantity !== null && (
              <span>Qty: {group.final_quantity}</span>
            )}
            {formattedDim && formattedDim !== "—" && (
              <span className="truncate max-w-[280px]">Dim: {formattedDim}</span>
            )}
            {formattedFin && formattedFin !== "—" && (
              <span className="truncate max-w-[200px]">Fin: {formattedFin}</span>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 justify-between sm:justify-end">
        {openIssues > 0 && (
          <div className="flex items-center gap-1.5 text-xs font-medium text-amber-600 bg-amber-50 px-2.5 py-1 rounded-md border border-amber-200">
            <AlertCircle className="h-3.5 w-3.5" />
            <span>{openIssues} Open Issue{openIssues > 1 ? "s" : ""}</span>
          </div>
        )}
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-50 text-slate-400 group-hover:bg-[#0EA5E9]/10 group-hover:text-[#0EA5E9] transition-colors">
          <ChevronRight className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

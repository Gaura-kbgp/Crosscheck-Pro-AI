import React, { useMemo, useState } from "react";
import { MatchGroup } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { ChevronRight, ChevronDown, AlertCircle, Filter, X } from "lucide-react";
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

  // Group by canonical_sku so TUKT ×16, SM96 ×8, etc. collapse into one row
  const skuGroups = useMemo(() => {
    const map = new Map<string, MatchGroup[]>();
    for (const g of filteredGroups) {
      const sku = g.canonical_sku || "Unknown SKU";
      if (!map.has(sku)) map.set(sku, []);
      map.get(sku)!.push(g);
    }
    return Array.from(map.entries());
  }, [filteredGroups]);

  const [expandedSkus, setExpandedSkus] = useState<Set<string>>(new Set());
  const toggleSku = (sku: string) =>
    setExpandedSkus((prev) => {
      const next = new Set(prev);
      next.has(sku) ? next.delete(sku) : next.add(sku);
      return next;
    });

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
        skuGroups.map(([sku, grps]) => {
          if (grps.length === 1) {
            return (
              <MatchGroupCard
                key={grps[0].id}
                group={grps[0]}
                onClick={() => onSelectGroup(grps[0].id)}
              />
            );
          }
          const isExpanded = expandedSkus.has(sku);
          return (
            <div key={sku} className="rounded-xl border border-[#DCE6F0] bg-white shadow-2xs overflow-hidden">
              <SkuGroupHeader
                sku={sku}
                groups={grps}
                expanded={isExpanded}
                onToggle={() => toggleSku(sku)}
              />
              {isExpanded && (
                <div className="divide-y divide-[#F0F4F8]">
                  {grps.map((g) => (
                    <MatchGroupCard
                      key={g.id}
                      group={g}
                      onClick={() => onSelectGroup(g.id)}
                      nested
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

function SkuGroupHeader({
  sku,
  groups,
  expanded,
  onToggle,
}: {
  sku: string;
  groups: MatchGroup[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const statusCounts = groups.reduce<Record<string, number>>((acc, g) => {
    acc[g.status] = (acc[g.status] || 0) + 1;
    return acc;
  }, {});

  const STATUS_ORDER = ["MISSING", "EXTRA", "CHANGED", "UNCERTAIN", "OUT_OF_SCOPE", "MATCHED"];
  const dominantStatus = STATUS_ORDER.find((s) => statusCounts[s]) || "MATCHED";

  const hasCritical = groups.some((g) =>
    g.discrepancies.some((d) => d.severity === "CRITICAL")
  );

  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        "w-full flex items-center justify-between gap-4 px-4 py-3 text-left hover:bg-[#F7F9FC] transition-colors",
        hasCritical && "bg-rose-50/30"
      )}
    >
      <div className="flex items-center gap-3 min-w-0">
        <StatusBadge status={dominantStatus} />
        <span className="text-base font-bold text-[#0F2747] font-mono tracking-tight truncate">
          {sku}
        </span>
        <span className="shrink-0 text-xs font-semibold text-[#58708F] bg-slate-100 px-2 py-0.5 rounded-full">
          {groups.length} groups
        </span>
        <div className="hidden sm:flex items-center gap-1.5 flex-wrap">
          {STATUS_ORDER.filter((s) => statusCounts[s]).map((s) => (
            <span key={s} className="text-[10px] font-semibold text-[#58708F]">
              {s} ×{statusCounts[s]}
            </span>
          ))}
        </div>
      </div>
      {expanded ? (
        <ChevronDown className="h-4 w-4 shrink-0 text-[#58708F]" />
      ) : (
        <ChevronRight className="h-4 w-4 shrink-0 text-[#58708F]" />
      )}
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls = {
    MATCHED: "bg-emerald-100 text-emerald-700",
    CHANGED: "bg-amber-100 text-amber-700",
    MISSING: "bg-rose-100 text-rose-700",
    EXTRA: "bg-purple-100 text-purple-700",
    OUT_OF_SCOPE: "bg-sky-100 text-sky-700",
  }[status] ?? "bg-slate-100 text-slate-700";
  return (
    <Badge className={cn("px-2.5 py-1 text-xs font-bold shadow-none border-none shrink-0", cls)}>
      {status}
    </Badge>
  );
}

function MatchGroupCard({
  group,
  onClick,
  nested = false,
}: {
  group: MatchGroup;
  onClick: () => void;
  nested?: boolean;
}) {
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
        "group relative flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 transition-all cursor-pointer",
        nested
          ? "hover:bg-[#F7F9FC]"
          : "rounded-xl border border-[#DCE6F0] bg-white shadow-2xs hover:border-[#0EA5E9] hover:shadow-md",
        hasCritical && !nested && "border-rose-200 bg-rose-50/10",
        hasCritical && nested && "bg-rose-50/10"
      )}
    >
      <div className="flex items-center gap-4">
        <StatusBadge status={group.status} />
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

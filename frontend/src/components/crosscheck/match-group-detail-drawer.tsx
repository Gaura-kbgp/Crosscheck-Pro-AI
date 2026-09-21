import React, { useState } from "react";
import { MatchGroup, Discrepancy } from "@/lib/api/types";
import { X, AlertCircle, ArrowRight, CheckCircle2, XCircle, FileCheck2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatDisplayValue } from "@/lib/utils/formatters";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reviewApi } from "@/lib/api/endpoints";

interface MatchGroupDetailDrawerProps {
  group: MatchGroup | null;
  isOpen: boolean;
  onClose: () => void;
}

export function MatchGroupDetailDrawer({ group, isOpen, onClose }: MatchGroupDetailDrawerProps) {
  const queryClient = useQueryClient();
  const [processingId, setProcessingId] = useState<string | null>(null);

  const reviewMutation = useMutation({
    mutationFn: async ({ discrepancyId, action }: { discrepancyId: string; action: any }) => {
      setProcessingId(discrepancyId);
      return await reviewApi.submitAction(discrepancyId, { action, reason: "Reviewed via workspace drawer" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries();
      setProcessingId(null);
    },
    onError: () => {
      setProcessingId(null);
    },
  });

  if (!isOpen || !group) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "MATCHED":
        return "bg-emerald-100 text-emerald-700";
      case "CHANGED":
        return "bg-amber-100 text-amber-700";
      case "MISSING":
        return "bg-rose-100 text-rose-700";
      case "EXTRA":
        return "bg-purple-100 text-purple-700";
      default:
        return "bg-slate-100 text-slate-700";
    }
  };

  const discrepancies = group.discrepancies || [];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs transition-opacity"
      onClick={handleBackdropClick}
      aria-modal="true"
      role="dialog"
    >
      <div
        className="w-full max-w-2xl bg-[#F7F9FC] h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-300 border-l border-[#DCE6F0]"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#DCE6F0] bg-white">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-[#0F2747] font-mono">
              {group.canonical_sku || "Unknown SKU"}
            </h2>
            <Badge className={cn("px-2 py-0.5 text-xs font-bold shadow-none border-none", getStatusColor(group.status))}>
              {group.status}
            </Badge>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Summary Card */}
          <div className="rounded-xl border border-[#DCE6F0] bg-white p-5 shadow-2xs">
            <h3 className="text-xs font-bold text-[#58708F] mb-3 uppercase tracking-wider">Final Accepted Values</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-xs text-[#58708F] mb-1">Quantity</div>
                <div className="font-semibold text-[#0F2747]">{group.final_quantity ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs text-[#58708F] mb-1">Dimensions</div>
                <div className="font-semibold text-[#0F2747] font-mono text-xs">{formatDisplayValue(group.final_dimensions)}</div>
              </div>
              <div>
                <div className="text-xs text-[#58708F] mb-1">Finish</div>
                <div className="font-semibold text-[#0F2747]">{formatDisplayValue(group.final_finish)}</div>
              </div>
              <div>
                <div className="text-xs text-[#58708F] mb-1">Price</div>
                <div className="font-semibold text-[#0F2747]">
                  {group.final_unit_price ? `$${group.final_unit_price.toFixed(2)}` : "—"}
                </div>
              </div>
            </div>
          </div>

          {/* Discrepancies Section */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-[#0F2747] uppercase tracking-wider flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-500" />
              Identified Discrepancies ({discrepancies.length})
            </h3>

            {discrepancies.length === 0 ? (
              <div className="rounded-xl border border-[#DCE6F0] bg-white p-6 text-center shadow-2xs">
                <p className="text-[#58708F] text-sm">No discrepancies found for this item.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {discrepancies.map((d) => (
                  <DiscrepancyCard
                    key={d.id}
                    discrepancy={d}
                    isProcessing={processingId === d.id}
                    onAction={(action) => reviewMutation.mutate({ discrepancyId: d.id, action })}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-[#DCE6F0] bg-white p-4 px-6 flex justify-between items-center">
          <p className="text-xs text-[#58708F]">Review and audit discrepancies.</p>
          <div className="flex gap-3">
            <Button variant="outline" onClick={onClose} className="cursor-pointer">
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function DiscrepancyCard({
  discrepancy,
  isProcessing,
  onAction,
}: {
  discrepancy: Discrepancy;
  isProcessing: boolean;
  onAction: (action: string) => void;
}) {
  const isCritical = discrepancy.severity === "CRITICAL";
  const isOpen = discrepancy.status === "OPEN" || discrepancy.status === "ESCALATED";

  return (
    <div className={cn(
      "rounded-xl border bg-white overflow-hidden shadow-2xs space-y-3",
      isCritical ? "border-rose-200" : "border-[#DCE6F0]"
    )}>
      <div className={cn(
        "px-4 py-2.5 border-b flex justify-between items-center text-xs",
        isCritical ? "bg-rose-50/50 border-rose-200" : "bg-slate-50 border-[#DCE6F0]"
      )}>
        <div className="font-bold text-[#0F2747]">
          Field: <span className="font-mono text-sky-600 bg-sky-50 px-1.5 py-0.5 rounded capitalize">{discrepancy.field_name.replace("_", " ")}</span>
        </div>
        <div className="flex items-center gap-2">
          {discrepancy.introduced_at && (
            <div className="text-[11px] font-medium text-[#58708F] flex items-center gap-1 bg-white px-2 py-0.5 rounded border shadow-2xs">
              Introduced at: <span className="text-[#0F2747] font-bold">{discrepancy.introduced_at}</span>
            </div>
          )}
          <Badge className={cn(
            "text-[10px] uppercase shadow-none border-none tracking-wider",
            isCritical ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"
          )}>
            {discrepancy.severity}
          </Badge>
          <span className={cn(
            "text-[10px] font-bold px-2 py-0.5 rounded uppercase",
            isOpen ? "bg-amber-50 text-amber-700 border border-amber-200" : "bg-emerald-50 text-emerald-700 border border-emerald-200"
          )}>
            {discrepancy.status}
          </span>
        </div>
      </div>
      
      {discrepancy.explanation && (
        <p className="px-4 text-xs text-[#58708F]">
          {discrepancy.explanation}
        </p>
      )}

      <div className="px-4 pb-2 overflow-x-auto">
        <div className="flex items-start gap-3 min-w-max">
          <ValueBlock label="Design" value={discrepancy.design_value} />
          <ArrowRight className="h-4 w-4 text-slate-300 mt-5 shrink-0" />
          <ValueBlock label="Order" value={discrepancy.order_value} />
          <ArrowRight className="h-4 w-4 text-slate-300 mt-5 shrink-0" />
          <ValueBlock label="Acknowledgement" value={discrepancy.ack_value} />
        </div>
      </div>

      {/* Action Buttons */}
      <div className="px-4 py-2.5 bg-slate-50/70 border-t border-slate-100 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={isProcessing}
          onClick={() => onAction("ACCEPT_FINDING")}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 transition-colors disabled:opacity-50 cursor-pointer"
        >
          <CheckCircle2 className="h-3.5 w-3.5" />
          Accept Finding
        </button>

        <button
          type="button"
          disabled={isProcessing}
          onClick={() => onAction("FALSE_POSITIVE")}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors disabled:opacity-50 cursor-pointer"
        >
          <XCircle className="h-3.5 w-3.5" />
          Mark False Positive
        </button>

        <button
          type="button"
          disabled={isProcessing}
          onClick={() => onAction("ACKNOWLEDGE_MFR_CHANGE")}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 transition-colors disabled:opacity-50 cursor-pointer"
        >
          <FileCheck2 className="h-3.5 w-3.5" />
          Acknowledge Mfr Change
        </button>
      </div>
    </div>
  );
}

function ValueBlock({ label, value }: { label: string; value: any }) {
  const formatted = formatDisplayValue(value);
  const isMissing = formatted === "—" || formatted === "Missing" || formatted === "MISSING";
  return (
    <div className="w-36 flex-shrink-0">
      <div className="text-[10px] font-bold text-[#58708F] uppercase tracking-wider mb-1">{label}</div>
      <div className={cn(
        "p-2 rounded-lg border text-xs font-semibold font-mono break-words leading-relaxed",
        isMissing ? "bg-slate-50 border-slate-200 text-slate-400 italic" : "bg-white border-[#DCE6F0] text-[#0F2747]"
      )}>
        {formatted}
      </div>
    </div>
  );
}

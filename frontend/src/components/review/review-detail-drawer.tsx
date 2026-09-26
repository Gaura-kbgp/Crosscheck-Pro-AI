import React, { useState, useEffect } from "react";
import { Discrepancy, MatchGroup, ReviewActionType, SourceEvidence, CabinetClassification } from "@/lib/api/types";
import { X, ArrowRight, CheckCircle, XCircle, AlertTriangle, MessageSquareWarning, Edit3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useReviewAction } from "@/lib/hooks/use-reviews";
import { toast } from "sonner";
import { ReviewHistory } from "./review-history";
import { OverrideDataForm } from "./override-data-form";
import { formatDisplayValue } from "@/lib/utils/formatters";

interface ReviewDetailDrawerProps {
  discrepancy: Discrepancy | null;
  group: MatchGroup | null;
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  /** Advances to the next finding in the current list (or closes if none). Called after an action resolves this one, so a reviewer can move through the queue without clicking. */
  onNext?: () => void;
  readOnly?: boolean;
}

export function ReviewDetailDrawer({
  discrepancy,
  group,
  projectId,
  isOpen,
  onClose,
  onNext,
  readOnly = false,
}: ReviewDetailDrawerProps) {
  const [overrideOpen, setOverrideOpen] = useState(false);
  const actionMutation = useReviewAction(projectId);

  const handleAction = React.useCallback(async (action: ReviewActionType, reason?: string) => {
    if (!discrepancy) return;
    try {
      await actionMutation.mutateAsync({
        discrepancyId: discrepancy.id,
        data: { action, reason },
      });
      toast.success(`Discrepancy marked as ${action.replace(/_/g, " ")}`);
      if (action === "ACCEPT_FINDING" || action === "FALSE_POSITIVE" || action === "ESCALATE") {
        (onNext || onClose)();
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to perform review action");
    }
  }, [discrepancy, actionMutation, onNext, onClose]);

  // Keyboard shortcuts: A = Accept, F = False Positive, E = Escalate — lets a
  // reviewer move through the open findings queue without clicking each time.
  useEffect(() => {
    if (!isOpen || readOnly || overrideOpen) return;
    if (discrepancy?.status === "ACCEPTED" || discrepancy?.status === "FALSE_POSITIVE") return;

    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isTyping = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if (isTyping || e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        handleAction("ACCEPT_FINDING");
      } else if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        const reason = window.prompt("Reason for marking as false positive:");
        if (reason !== null) handleAction("FALSE_POSITIVE", reason);
      } else if (e.key === "e" || e.key === "E") {
        e.preventDefault();
        const reason = window.prompt("Reason for escalation:");
        if (reason !== null) handleAction("ESCALATE", reason);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, readOnly, overrideOpen, discrepancy, handleAction]);

  if (!isOpen || !discrepancy || !group) return null;

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
      case "ACKNOWLEDGED": return "bg-emerald-100 text-emerald-700";
      default: return "bg-slate-100 text-slate-700";
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs transition-opacity"
        onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
        aria-modal="true"
        role="dialog"
      >
        <div className="w-full max-w-2xl bg-[#F7F9FC] h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-300 border-l border-[#DCE6F0]">
          
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[#DCE6F0] bg-white">
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-[#0F2747] font-mono truncate max-wxs">
                {group.canonical_sku || "Unknown SKU"}
              </h2>
              <Badge className={cn("px-2 py-0.5 text-xs font-bold uppercase tracking-wider shadow-none border-none", getSeverityColor(discrepancy.severity))}>
                {discrepancy.severity}
              </Badge>
              <Badge className={cn("px-2 py-0.5 text-xs font-bold uppercase tracking-wider shadow-none border-none", getStatusColor(discrepancy.status))}>
                {discrepancy.status}
              </Badge>
            </div>
            <button
              onClick={onClose}
              className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Field Info & Introduced At */}
            <div className="bg-white rounded-xl border border-[#DCE6F0] shadow-2xs overflow-hidden">
              <div className="p-4 border-b border-[#DCE6F0] bg-slate-50 flex justify-between items-center">
                <div className="font-bold text-[#0F2747]">
                  Discrepant Field: <span className="font-mono text-sky-600 bg-sky-50 px-2 py-1 rounded">{discrepancy.field_name}</span>
                </div>
                {discrepancy.introduced_at && (
                  <div className="text-xs font-medium text-[#58708F] flex items-center gap-1.5 bg-white px-2 py-1 rounded-md border shadow-xs">
                    Introduced at: <span className="text-[#0F2747] font-bold">{discrepancy.introduced_at}</span>
                  </div>
                )}
              </div>

              {/* 3-way Comparison */}
              <div className="p-5 overflow-x-auto">
                <div className="flex items-start gap-4 min-w-max">
                  <ValueBlock label="Design" value={discrepancy.design_value} evidence={group.design_item?.source_metadata?.evidence} cabinetClassification={group.design_item?.cabinet_classification} />
                  <ArrowRight className="h-4 w-4 text-slate-300 mt-6 shrink-0" />
                  <ValueBlock label="Order" value={discrepancy.order_value} evidence={group.order_item?.source_metadata?.evidence} cabinetClassification={group.order_item?.cabinet_classification} />
                  <ArrowRight className="h-4 w-4 text-slate-300 mt-6 shrink-0" />
                  <ValueBlock label="Acknowledgement" value={discrepancy.ack_value} evidence={group.ack_item?.source_metadata?.evidence} cabinetClassification={group.ack_item?.cabinet_classification} />
                </div>
              </div>
            </div>

            {/* Review Actions (only if not readOnly and not fully resolved, though we can allow override always if needed, but usually we hide/disable if readOnly) */}
            {!readOnly && discrepancy.status !== "ACCEPTED" && discrepancy.status !== "FALSE_POSITIVE" && (
              <div className="bg-white rounded-xl border border-[#DCE6F0] shadow-2xs p-5 space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-bold text-[#0F2747] uppercase tracking-wider">Review Actions</h3>
                  <span className="text-[11px] text-[#58708F] font-medium">
                    Shortcuts: <kbd className="px-1 py-0.5 bg-slate-100 rounded border border-slate-200 font-mono">A</kbd> Accept ·{" "}
                    <kbd className="px-1 py-0.5 bg-slate-100 rounded border border-slate-200 font-mono">F</kbd> False Positive ·{" "}
                    <kbd className="px-1 py-0.5 bg-slate-100 rounded border border-slate-200 font-mono">E</kbd> Escalate
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Button
                    variant="outline"
                    className="justify-start gap-2 h-auto py-3 text-emerald-700 border-emerald-200 bg-emerald-50 hover:bg-emerald-100 hover:text-emerald-800"
                    onClick={() => handleAction("ACCEPT_FINDING")}
                    isLoading={actionMutation.isPending}
                  >
                    <CheckCircle className="h-4 w-4" />
                    <div className="text-left">
                      <div className="font-bold">Accept Finding</div>
                      <div className="text-xs opacity-80 font-normal">Mark this as a true discrepancy</div>
                    </div>
                  </Button>

                  <Button 
                    variant="outline" 
                    className="justify-start gap-2 h-auto py-3 text-slate-700 border-slate-200 bg-slate-50 hover:bg-slate-100 hover:text-slate-900"
                    onClick={() => {
                      const reason = window.prompt("Reason for marking as false positive:");
                      if (reason !== null) handleAction("FALSE_POSITIVE", reason);
                    }}
                    isLoading={actionMutation.isPending}
                  >
                    <XCircle className="h-4 w-4" />
                    <div className="text-left">
                      <div className="font-bold">False Positive</div>
                      <div className="text-xs opacity-80 font-normal">Ignore this finding</div>
                    </div>
                  </Button>

                  <Button 
                    variant="outline" 
                    className="justify-start gap-2 h-auto py-3 text-sky-700 border-sky-200 bg-sky-50 hover:bg-sky-100 hover:text-sky-800"
                    onClick={() => setOverrideOpen(true)}
                    isLoading={actionMutation.isPending}
                  >
                    <Edit3 className="h-4 w-4" />
                    <div className="text-left">
                      <div className="font-bold">Override Data</div>
                      <div className="text-xs opacity-80 font-normal">Manually set final value</div>
                    </div>
                  </Button>

                  <Button 
                    variant="outline" 
                    className="justify-start gap-2 h-auto py-3 text-amber-700 border-amber-200 bg-amber-50 hover:bg-amber-100 hover:text-amber-800"
                    onClick={() => {
                      const reason = window.prompt("Reason for acknowledging manufacturer change:");
                      if (reason !== null) handleAction("ACKNOWLEDGE_MFR_CHANGE", reason);
                    }}
                    isLoading={actionMutation.isPending}
                  >
                    <AlertTriangle className="h-4 w-4" />
                    <div className="text-left">
                      <div className="font-bold">Ack Mfr Change</div>
                      <div className="text-xs opacity-80 font-normal">Accept manufacturer adjustment</div>
                    </div>
                  </Button>

                  <Button 
                    variant="outline" 
                    className="justify-start gap-2 h-auto py-3 text-rose-700 border-rose-200 bg-rose-50 hover:bg-rose-100 hover:text-rose-800 sm:col-span-2"
                    onClick={() => {
                      const reason = window.prompt("Reason for escalation:");
                      if (reason !== null) handleAction("ESCALATE", reason);
                    }}
                    isLoading={actionMutation.isPending}
                  >
                    <MessageSquareWarning className="h-4 w-4" />
                    <div className="text-left">
                      <div className="font-bold">Escalate Issue</div>
                      <div className="text-xs opacity-80 font-normal">Flag for managerial review</div>
                    </div>
                  </Button>
                </div>
              </div>
            )}

            {/* Audit History */}
            <ReviewHistory projectId={projectId} resourceId={discrepancy.id} />
            <ReviewHistory projectId={projectId} resourceId={group.id} title="Match Group History" />
          </div>
        </div>
      </div>

      <OverrideDataForm
        isOpen={overrideOpen}
        onClose={() => setOverrideOpen(false)}
        discrepancy={discrepancy}
        group={group}
        projectId={projectId}
      />
    </>
  );
}

function ValueBlock({ label, value, evidence, cabinetClassification }: { label: string; value: string | null | undefined; evidence?: SourceEvidence | null; cabinetClassification?: CabinetClassification | null }) {
  const displayVal = formatDisplayValue(value);
  const isMissing = displayVal === "—" || displayVal === "" || !value || value === "null";
  return (
    <div className="w-36 flex-shrink-0">
      <div className="text-[11px] font-bold text-[#58708F] uppercase tracking-wider mb-1.5">{label}</div>
      <div className={cn(
        "p-3 rounded-lg border text-sm font-mono break-words shadow-xs",
        isMissing ? "bg-slate-50 border-slate-200 text-slate-400 italic font-medium font-sans" : "bg-white border-[#DCE6F0] text-[#0F2747] font-semibold"
      )}>
        {isMissing ? "Not specified" : displayVal}
      </div>
      {/* F8.3 Phase 2/3: minimal source traceability — page number + whether the
          extracted value was verified (single-source page-text match, or
          Phase 3 two-source OCR+Vision agreement). */}
      {evidence && (evidence.page_number || evidence.status) && (
        <div
          className={cn(
            "mt-1 text-[10px] font-medium truncate",
            evidence.status === "VERIFIED" ? "text-emerald-600" : "text-amber-600"
          )}
          title={evidence.source_text || undefined}
        >
          {evidence.page_number ? `Page ${evidence.page_number}` : "Source"} · {evidence.status === "VERIFIED" ? "verified" : "unverified"}
        </div>
      )}
      {/* F8.3 Phase 3: explicit OCR vs Vision conflict — both raw readings shown, never silently picked. */}
      {evidence?.verification?.conflicts && evidence.verification.conflicts.length > 0 && (
        <div className="mt-1.5 rounded border border-amber-200 bg-amber-50 p-1.5 text-[10px] text-amber-800 space-y-0.5">
          <div className="font-bold flex items-center gap-1">⚠ Extraction conflict</div>
          {evidence.verification.conflicts.map((c, i) => (
            <div key={i} className="truncate">
              <span className="font-semibold">{c.field}:</span> OCR={String(c.ocr_value)} / Vision={String(c.vision_value)}
            </div>
          ))}
        </div>
      )}
      {/* Cabinet Code Intelligence: concise reason for the category/confidence
          decision — never raw model reasoning, just the reason codes (§27). */}
      {cabinetClassification && (cabinetClassification.confidence_level === "HIGH" || cabinetClassification.confidence_level === "UNCERTAIN" || !cabinetClassification.is_cabinet_candidate) && (
        <div
          className={cn(
            "mt-1.5 rounded border p-1.5 text-[10px] space-y-0.5",
            cabinetClassification.confidence_level === "HIGH"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : cabinetClassification.confidence_level === "UNCERTAIN"
              ? "border-amber-200 bg-amber-50 text-amber-800"
              : "border-slate-200 bg-slate-50 text-slate-600"
          )}
        >
          <div className="font-bold flex items-center gap-1">
            {cabinetClassification.confidence_level === "HIGH" ? "✓" : cabinetClassification.confidence_level === "UNCERTAIN" ? "⚠" : "ℹ"}{" "}
            {cabinetClassification.classification}
            {!cabinetClassification.is_cabinet_candidate ? " (excluded)" : ""}
          </div>
          {cabinetClassification.reason_codes && cabinetClassification.reason_codes.length > 0 && (
            <div className="truncate" title={cabinetClassification.reason_codes.join(", ")}>
              {cabinetClassification.reason_codes.join(", ")}
            </div>
          )}
          {cabinetClassification.candidate_variants && cabinetClassification.candidate_variants.length > 1 && (
            <div className="truncate" title={cabinetClassification.candidate_variants.join(" / ")}>
              Variants: {cabinetClassification.candidate_variants.join(" / ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

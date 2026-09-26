"use client";

import React from "react";
import Link from "next/link";
import { ProcessingStage } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  GitCompare,
  X,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ProcessingStatusCardProps {
  status: ProcessingStage;
  error?: Record<string, unknown> | null;
  projectId?: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  onCancel?: () => void;
  isCancelling?: boolean;
  className?: string;
}

const STAGES: {
  key: ProcessingStage;
  label: string;
  description: string;
}[] = [
  { key: "QUEUED", label: "Queued", description: "Job scheduled in pipeline queue" },
  { key: "VALIDATING", label: "Validating documents", description: "Verifying PDF structure and layout" },
  { key: "EXTRACTING", label: "Extracting document data", description: "Running AI candidate extraction" },
  { key: "NORMALIZING", label: "Normalizing data", description: "Standardizing codes, dimensions & finishes" },
  { key: "MATCHING", label: "Matching items", description: "Correlating 3-way SKU line items" },
  { key: "COMPARING", label: "Comparing documents", description: "Evaluating discrepancies & tolerances" },
  { key: "GENERATING_DISCREPANCIES", label: "Checking for discrepancies", description: "Calculating severity and review flags" },
  { key: "COMPLETED", label: "Ready for review", description: "Three-way verification complete" },
];

export function ProcessingStatusCard({
  status,
  error,
  projectId,
  onRetry,
  onDismiss,
  onCancel,
  isCancelling,
  className,
}: ProcessingStatusCardProps) {
  const isFailed = status === "FAILED";
  const isCompleted = status === "COMPLETED";
  const isRunning = !isFailed && !isCompleted;

  // Find index in stages
  const currentStageIndex = STAGES.findIndex((s) => s.key === status);
  const activeStage =
    STAGES.find((s) => s.key === status) || {
      key: status,
      label: status.toLowerCase().replace(/_/g, " "),
      description: "Processing pipeline active",
    };

  const rawErrorStr = typeof error === "string" ? error : JSON.stringify(error || {});
  // F8.3: non-fatal, per-document extraction completeness warnings. Present
  // only when the job COMPLETED but a document couldn't be fully verified
  // (empty extraction, line-number gaps) — never a failure, just a review flag.
  const extractionWarnings: { document_type: string; issues?: { message: string }[] }[] =
    error && Array.isArray((error as Record<string, unknown>).warnings)
      ? ((error as Record<string, unknown>).warnings as { document_type: string; issues?: { message: string }[] }[])
      : [];
  const isGeminiQuotaError =
    rawErrorStr.includes("RESOURCE_EXHAUSTED") ||
    rawErrorStr.includes("prepayment credits") ||
    rawErrorStr.includes("429");

  return (
    <div
      className={cn(
        "rounded-xl border p-5 sm:p-6 shadow-2xs space-y-5 transition-all relative",
        isCompleted && "border-[#BBF7D0] bg-white",
        isRunning && "border-[#E9D5FF] bg-white",
        isFailed && "border-[#FECACA] bg-[#FEE2E2]/30",
        className
      )}
    >
      {/* Dismiss button on top-right */}
      {onDismiss && (isFailed || isCompleted) && (
        <button
          type="button"
          onClick={onDismiss}
          className="absolute top-3.5 right-3.5 p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          title="Dismiss notification"
        >
          <X className="h-4 w-4" />
        </button>
      )}

      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pr-6">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
              isCompleted && "bg-[#DCFCE7] text-[#16A34A]",
              isRunning && "bg-[#F3E8FF] text-[#7C3AED]",
              isFailed && "bg-[#FEE2E2] text-[#DC2626]"
            )}
          >
            {isRunning && <Loader2 className="h-6 w-6 animate-spin" />}
            {isCompleted && <CheckCircle2 className="h-6 w-6" />}
            {isFailed && <AlertCircle className="h-6 w-6" />}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "text-[11px] font-bold uppercase tracking-wider",
                  isFailed ? "text-[#DC2626]" : isCompleted ? "text-[#16A34A]" : "text-[#7C3AED]"
                )}
              >
                {isRunning ? "Automated Pipeline Active" : isCompleted ? "Verification Complete" : "Pipeline Error"}
              </span>
            </div>
            <h3 className="text-base font-bold text-[#0F2747]">
              {activeStage.label}
            </h3>
            <p className="text-xs text-[#58708F] mt-0.5">
              {activeStage.description}
            </p>
          </div>
        </div>

        {/* Action button */}
        <div className="shrink-0 flex items-center gap-2">
          {isCompleted && (
            <Link href={`/projects/${projectId}/crosscheck`}>
              <Button variant="default" size="sm" className="gap-1.5 font-semibold bg-[#0EA5E9] hover:bg-[#0284C7]">
                <GitCompare className="h-4 w-4" />
                <span>Open Cross-Check Matrix</span>
              </Button>
            </Link>
          )}

          {isFailed && onRetry && (
            <Button
              variant="default"
              size="sm"
              onClick={onRetry}
              className="font-bold bg-[#0EA5E9] hover:bg-[#0284C7] text-white shadow-xs gap-1.5"
            >
              <Sparkles className="h-4 w-4" />
              <span>Retry with OpenAI GPT-4o</span>
            </Button>
          )}

          {isRunning && onCancel && (
            <Button
              variant="outline"
              size="sm"
              onClick={onCancel}
              disabled={isCancelling}
              className="font-semibold border-[#FECACA] text-[#DC2626] hover:bg-[#FEE2E2] gap-1.5"
            >
              <X className="h-4 w-4" />
              <span>{isCancelling ? "Cancelling..." : "Cancel"}</span>
            </Button>
          )}
        </div>
      </div>

      {/* Progress Stepper for Running / Completed State */}
      {!isFailed && (
        <div className="space-y-3 pt-2 border-t border-[#DCE6F0]">
          <div className="flex items-center justify-between text-xs font-semibold text-[#58708F]">
            <span>Pipeline Progress</span>
            <span>
              {isCompleted
                ? "100% Completed"
                : `${Math.max(1, currentStageIndex + 1)} of ${STAGES.length} stages`}
            </span>
          </div>

          {/* Progress Bar */}
          <div className="h-2 w-full rounded-full bg-[#F3E8FF] overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                isCompleted ? "bg-[#16A34A] w-full" : "bg-[#7C3AED]"
              )}
              style={{
                width: isCompleted
                  ? "100%"
                  : `${Math.max(15, ((currentStageIndex + 1) / STAGES.length) * 100)}%`,
              }}
            />
          </div>

          {/* Stepper pills */}
          <div className="hidden md:grid md:grid-cols-4 gap-2 pt-1">
            {STAGES.slice(1, 5).map((stage) => {
              const stageIdx = STAGES.findIndex((s) => s.key === stage.key);
              const isPassed = currentStageIndex > stageIdx || isCompleted;
              const isCurrent = currentStageIndex === stageIdx && !isCompleted;

              return (
                <div
                  key={stage.key}
                  className={cn(
                    "rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition-colors",
                    isPassed && "border-[#BBF7D0] bg-[#DCFCE7]/40 text-[#15803D]",
                    isCurrent && "border-[#7C3AED] bg-[#F3E8FF] text-[#6D28D9] font-semibold animate-pulse",
                    !isPassed && !isCurrent && "border-[#DCE6F0] bg-[#F7F9FC] text-[#58708F]"
                  )}
                >
                  <span className="truncate block">{stage.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Error Details */}
      {isFailed && (
        <div className="rounded-lg border border-[#FECACA] bg-white p-3.5 text-xs text-[#B91C1C] space-y-2">
          {isGeminiQuotaError ? (
            <div>
              <p className="font-bold text-slate-800">
                AI Provider Switched to OpenAI GPT-4o
              </p>
              <p className="text-slate-600 mt-1 leading-relaxed">
                The previous run failed because Google Gemini API quota was exhausted. The backend has now been switched to OpenAI.
                Please ensure you have provided your <code className="bg-slate-100 px-1 py-0.5 rounded text-[#0F2747] font-mono">OPENAI_API_KEY</code> in <code className="bg-slate-100 px-1 py-0.5 rounded text-[#0F2747] font-mono">backend/.env</code> and click <strong>Retry with OpenAI GPT-4o</strong> above.
              </p>
            </div>
          ) : (
            <div>
              <p className="font-semibold">Error Message:</p>
              <p className="font-mono text-[11px] break-all mt-1">
                {rawErrorStr}
              </p>
            </div>
          )}
        </div>
      )}

      {/* F8.3: Completed with extraction warnings — pipeline finished, but one or
          more documents could not be fully verified and should be reviewed. */}
      {isCompleted && extractionWarnings.length > 0 && (
        <div className="rounded-lg border border-[#FDE68A] bg-[#FFFBEB] p-3.5 text-xs text-[#92400E] space-y-2">
          <p className="font-bold">
            Extraction completed. Please review the flagged items below before finalizing.
          </p>
          <ul className="space-y-1.5">
            {extractionWarnings.map((w, i) => (
              <li key={i}>
                <span className="font-semibold">{w.document_type}:</span>{" "}
                {(w.issues || []).map((iss) => iss.message).join(" ")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

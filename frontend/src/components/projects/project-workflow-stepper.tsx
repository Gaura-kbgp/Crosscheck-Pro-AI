import React from "react";
import { ProjectStatus } from "@/lib/api/types";
import { Check, Upload, Cog, GitCompare, ShieldCheck, FileText, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProjectWorkflowStepperProps {
  status: ProjectStatus;
  isAllUploaded: boolean;
}

type StepState = "done" | "current" | "upcoming" | "error";

const STEPS = [
  { key: "upload", label: "Upload Documents", icon: Upload },
  { key: "process", label: "Processing", icon: Cog },
  { key: "review", label: "Review Findings", icon: GitCompare },
  { key: "finalize", label: "Finalize", icon: ShieldCheck },
  { key: "report", label: "Report", icon: FileText },
] as const;

/**
 * One horizontal progress line for the whole project lifecycle — upload
 * through final report — so a user always knows where they are and what
 * comes next, instead of reading four same-weight buttons and guessing.
 */
export function ProjectWorkflowStepper({ status, isAllUploaded }: ProjectWorkflowStepperProps) {
  const getStepState = (key: (typeof STEPS)[number]["key"]): StepState => {
    if (status === "FAILED" && key === "process") return "error";

    switch (key) {
      case "upload":
        if (isAllUploaded) return "done";
        return status === "DRAFT" ? "current" : "done";
      case "process":
        if (status === "DRAFT") return "upcoming";
        if (status === "PROCESSING") return "current";
        if (status === "FAILED") return "error";
        return "done"; // REVIEW_REQUIRED, COMPLETED, FINALIZED
      case "review":
        if (status === "REVIEW_REQUIRED") return "current";
        if (status === "COMPLETED" || status === "FINALIZED") return "done";
        return "upcoming";
      case "finalize":
        if (status === "FINALIZED") return "done";
        if (status === "COMPLETED") return "current";
        return "upcoming";
      case "report":
        if (status === "FINALIZED") return "current";
        return "upcoming";
      default:
        return "upcoming";
    }
  };

  return (
    <div className="flex items-center overflow-x-auto py-1">
      {STEPS.map((step, idx) => {
        const state = getStepState(step.key);
        const Icon = state === "error" ? AlertTriangle : step.icon;
        const isLast = idx === STEPS.length - 1;

        return (
          <React.Fragment key={step.key}>
            <div className="flex flex-col items-center shrink-0 w-24">
              <div
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full border-2 transition-colors",
                  state === "done" && "bg-[#16A34A] border-[#16A34A] text-white",
                  state === "current" && "bg-[#0EA5E9] border-[#0EA5E9] text-white animate-pulse",
                  state === "upcoming" && "bg-white border-[#DCE6F0] text-[#AFC0D3]",
                  state === "error" && "bg-rose-500 border-rose-500 text-white"
                )}
              >
                {state === "done" ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
              </div>
              <span
                className={cn(
                  "mt-1.5 text-[10px] font-semibold text-center leading-tight",
                  state === "current" ? "text-[#0F2747]" : "text-[#58708F]",
                  state === "error" && "text-rose-600"
                )}
              >
                {step.label}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  "h-0.5 flex-1 min-w-6 -mt-5",
                  state === "done" ? "bg-[#16A34A]" : "bg-[#DCE6F0]"
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

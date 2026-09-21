import React from "react";
import { Badge } from "@/components/ui/badge";
import {
  CrossCheckStatus,
  ProjectStatus,
  ProcessingStage,
  ReviewStatus,
  Severity,
} from "@/lib/api/types";
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  PlusCircle,
  MinusCircle,
  Clock,
  Loader2,
  XCircle,
  ShieldAlert,
  Info,
  Check,
  Lock,
} from "lucide-react";

export function CrossCheckStatusBadge({ status }: { status: CrossCheckStatus }) {
  switch (status) {
    case "MATCHED":
      return (
        <Badge variant="success" className="gap-1 font-semibold">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Matched
        </Badge>
      );
    case "CHANGED":
      return (
        <Badge variant="warning" className="gap-1 font-semibold">
          <AlertTriangle className="h-3.5 w-3.5" />
          Changed
        </Badge>
      );
    case "MISSING":
      return (
        <Badge variant="destructive" className="gap-1 font-semibold">
          <MinusCircle className="h-3.5 w-3.5" />
          Missing
        </Badge>
      );
    case "EXTRA":
      return (
        <Badge variant="purple" className="gap-1 font-semibold">
          <PlusCircle className="h-3.5 w-3.5" />
          Extra
        </Badge>
      );
    case "UNCERTAIN":
      return (
        <Badge variant="secondary" className="gap-1 font-semibold">
          <HelpCircle className="h-3.5 w-3.5" />
          Uncertain
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  switch (severity) {
    case "CRITICAL":
      return (
        <Badge variant="destructive" className="gap-1 font-semibold uppercase text-[10px]">
          <ShieldAlert className="h-3 w-3" />
          Critical
        </Badge>
      );
    case "HIGH":
      return (
        <Badge variant="destructive" className="gap-1 font-semibold uppercase text-[10px] bg-rose-50 text-rose-700">
          <AlertTriangle className="h-3 w-3" />
          High
        </Badge>
      );
    case "WARNING":
      return (
        <Badge variant="warning" className="gap-1 font-semibold uppercase text-[10px]">
          <AlertTriangle className="h-3 w-3" />
          Warning
        </Badge>
      );
    case "INFO":
      return (
        <Badge variant="info" className="gap-1 font-semibold uppercase text-[10px]">
          <Info className="h-3 w-3" />
          Info
        </Badge>
      );
    default:
      return <Badge variant="outline">{severity}</Badge>;
  }
}

export function ReviewStatusBadge({ status }: { status: ReviewStatus }) {
  switch (status) {
    case "OPEN":
      return (
        <Badge variant="warning" dot dotColor="bg-amber-500">
          Open
        </Badge>
      );
    case "ACCEPTED":
      return (
        <Badge variant="success" className="gap-1">
          <Check className="h-3 w-3" />
          Accepted
        </Badge>
      );
    case "FALSE_POSITIVE":
      return (
        <Badge variant="secondary" className="text-slate-600">
          False Positive
        </Badge>
      );
    case "ESCALATED":
      return (
        <Badge variant="destructive" className="gap-1">
          <ShieldAlert className="h-3 w-3" />
          Escalated
        </Badge>
      );
    case "ACKNOWLEDGED":
      return (
        <Badge variant="info" className="gap-1">
          <CheckCircle2 className="h-3 w-3" />
          Acknowledged
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  switch (status) {
    case "DRAFT":
      return (
        <Badge variant="secondary" className="gap-1">
          <Clock className="h-3 w-3 text-[#475569]" />
          Draft
        </Badge>
      );
    case "PROCESSING":
      return (
        <Badge variant="purple" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin text-[#6D28D9]" />
          Processing
        </Badge>
      );
    case "REVIEW_REQUIRED":
      return (
        <Badge variant="warning" className="gap-1">
          <AlertTriangle className="h-3 w-3 text-[#B45309]" />
          Review Required
        </Badge>
      );
    case "COMPLETED":
      return (
        <Badge variant="success" className="gap-1">
          <CheckCircle2 className="h-3 w-3 text-[#15803D]" />
          Completed
        </Badge>
      );
    case "FINALIZED":
      return (
        <Badge variant="default" className="gap-1 bg-[#0F2747] text-white">
          <Lock className="h-3 w-3 text-slate-300" />
          Finalized
        </Badge>
      );
    case "FAILED":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3 text-[#B91C1C]" />
          Failed
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export function ProcessingStageBadge({ stage }: { stage: ProcessingStage }) {
  const isFinished = stage === "COMPLETED";
  const isFailed = stage === "FAILED";

  if (isFinished) {
    return (
      <Badge variant="success" className="gap-1">
        <CheckCircle2 className="h-3 w-3 text-[#15803D]" />
        Completed
      </Badge>
    );
  }

  if (isFailed) {
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle className="h-3 w-3 text-[#B91C1C]" />
        Failed
      </Badge>
    );
  }

  const stageLabels: Record<ProcessingStage, string> = {
    QUEUED: "Queued",
    VALIDATING: "Validating Files",
    EXTRACTING: "Extracting Data",
    NORMALIZING: "Normalizing SKUs",
    MATCHING: "Cross-Checking Items",
    COMPARING: "Comparing Dimensions & Quantities",
    GENERATING_DISCREPANCIES: "Detecting Discrepancies",
    COMPLETED: "Completed",
    FAILED: "Failed",
  };

  return (
    <Badge variant="purple" className="gap-1.5">
      <Loader2 className="h-3 w-3 animate-spin text-[#6D28D9]" />
      {stageLabels[stage] || stage}
    </Badge>
  );
}

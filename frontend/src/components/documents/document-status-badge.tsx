"use client";

import React from "react";
import { DocumentStatus } from "@/lib/api/types";
import { Loader2, AlertCircle, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
  className?: string;
  showSpinner?: boolean;
}

export function DocumentStatusBadge({
  status,
  className,
  showSpinner = true,
}: DocumentStatusBadgeProps) {
  switch (status) {
    case "COMPLETED":
      return (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]",
            className
          )}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-[#16A34A]" />
          <span>Ready</span>
        </span>
      );

    case "PROCESSING":
    case "UPLOADED":
      return (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border bg-[#F3E8FF] text-[#6D28D9] border-[#E9D5FF]",
            className
          )}
        >
          {showSpinner ? (
            <Loader2 className="h-3 w-3 animate-spin text-[#7E22CE]" />
          ) : (
            <Clock className="h-3 w-3 text-[#7E22CE]" />
          )}
          <span>Processing</span>
        </span>
      );

    case "FAILED":
      return (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border bg-[#FEE2E2] text-[#B91C1C] border-[#FECACA]",
            className
          )}
        >
          <AlertCircle className="h-3 w-3 text-[#DC2626]" />
          <span>Failed</span>
        </span>
      );

    default:
      return (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border bg-slate-100 text-slate-700 border-slate-200",
            className
          )}
        >
          <span>{status}</span>
        </span>
      );
  }
}

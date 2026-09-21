"use client";

import React from "react";
import { Document, DocumentType } from "@/lib/api/types";
import { Check, Compass, ShoppingCart, CheckCircle2, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProjectDocumentWorkflowProps {
  documents: Document[];
  className?: string;
}

const workflowSteps: {
  step: number;
  type: DocumentType;
  title: string;
  shortDesc: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  {
    step: 1,
    type: "DESIGN",
    title: "Design Document",
    shortDesc: "Architectural & CAD specification",
    icon: Compass,
  },
  {
    step: 2,
    type: "ORDER",
    title: "Purchase Order",
    shortDesc: "Dealer / Client purchase contract",
    icon: ShoppingCart,
  },
  {
    step: 3,
    type: "ACKNOWLEDGEMENT",
    title: "Manufacturer Acknowledgement",
    shortDesc: "Factory confirmed order acknowledgement",
    icon: CheckCircle2,
  },
];

export function ProjectDocumentWorkflow({
  documents,
  className,
}: ProjectDocumentWorkflowProps) {
  // Map uploaded types
  const uploadedTypes = new Set(documents.map((d) => d.document_type));
  const uploadedCount = workflowSteps.filter((s) => uploadedTypes.has(s.type)).length;
  const isAllUploaded = uploadedCount === 3;

  return (
    <div
      className={cn(
        "rounded-xl border border-[#DCE6F0] bg-white p-5 sm:p-6 shadow-2xs space-y-4",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-[#DCE6F0] pb-4">
        <div>
          <h2 className="text-base font-bold text-[#0F2747]">
            Document Verification Workflow
          </h2>
          <p className="text-xs text-[#58708F] mt-0.5">
            Upload the three required documents to run automated three-way cross-check and discrepancy analysis.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border",
              isAllUploaded
                ? "bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]"
                : "bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]"
            )}
          >
            {isAllUploaded ? (
              <>
                <Check className="h-3.5 w-3.5" />
                <span>Ready for Verification ({uploadedCount}/3)</span>
              </>
            ) : (
              <span>{uploadedCount} of 3 Documents Uploaded</span>
            )}
          </span>
        </div>
      </div>

      {/* Connected Step Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 relative">
        {workflowSteps.map((stepItem, index) => {
          const isUploaded = uploadedTypes.has(stepItem.type);

          return (
            <div
              key={stepItem.type}
              className={cn(
                "relative flex items-center gap-3.5 rounded-lg border p-3.5 transition-colors",
                isUploaded
                  ? "border-[#BBF7D0] bg-[#DCFCE7]/30"
                  : "border-[#DCE6F0] bg-[#F7F9FC]/60"
              )}
            >
              {/* Step / Status Badge Icon */}
              <div
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg font-bold text-xs transition-colors",
                  isUploaded
                    ? "bg-[#16A34A] text-white shadow-2xs"
                    : "border border-[#DCE6F0] bg-white text-[#58708F]"
                )}
              >
                {isUploaded ? (
                  <Check className="h-4 w-4 stroke-[2.5]" />
                ) : (
                  <span>{stepItem.step}</span>
                )}
              </div>

              {/* Title & Type */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-1">
                  <span
                    className={cn(
                      "text-xs font-bold truncate",
                      isUploaded ? "text-[#0F2747]" : "text-[#0F2747]"
                    )}
                  >
                    {stepItem.title}
                  </span>
                </div>
                <p className="text-[11px] text-[#58708F] truncate mt-0.5">
                  {stepItem.shortDesc}
                </p>
              </div>

              {/* Step indicator arrow for desktop */}
              {index < 2 && (
                <div className="hidden md:block absolute -right-2.5 top-1/2 -translate-y-1/2 z-10 text-[#DCE6F0] bg-white rounded-full p-0.5 border border-[#DCE6F0]">
                  <ChevronRight className="h-3.5 w-3.5 text-[#58708F]" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

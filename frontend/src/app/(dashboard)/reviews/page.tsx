"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { useProjects } from "@/lib/hooks/use-projects";
import { useCrossCheck } from "@/lib/hooks/use-crosscheck";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reviewApi } from "@/lib/api/endpoints";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/feedback/empty-state";
import { 
  CheckSquare, 
  AlertOctagon, 
  AlertTriangle, 
  Info, 
  CheckCircle2, 
  XCircle, 
  ArrowUpRight, 
  ShieldAlert,
  FolderKanban,
  FileCheck2,
  Clock
} from "lucide-react";

import { formatDisplayValue } from "@/lib/utils/formatters";

export default function ReviewsQueuePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: projects, isLoading: isProjectsLoading } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [processingDiscrepancyId, setProcessingDiscrepancyId] = useState<string | null>(null);

  const activeProjectId = selectedProjectId || (projects && projects.length > 0 ? projects[0].id : null);
  const activeProject = projects?.find((p) => p.id === activeProjectId) || null;

  const {
    data: crosscheck,
    isLoading: isCrossCheckLoading,
    refetch: refetchCrossCheck,
  } = useCrossCheck(activeProjectId || undefined);

  const reviewMutation = useMutation({
    mutationFn: async ({ discrepancyId, action, reason }: { discrepancyId: string; action: any; reason?: string }) => {
      setProcessingDiscrepancyId(discrepancyId);
      return await reviewApi.submitAction(discrepancyId, { action, reason: reason || "Reviewed by auditor" });
    },
    onSuccess: () => {
      refetchCrossCheck();
      queryClient.invalidateQueries({ queryKey: ["projects", activeProjectId, "crosscheck"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setProcessingDiscrepancyId(null);
    },
    onError: () => {
      setProcessingDiscrepancyId(null);
    },
  });

  if (isProjectsLoading) {
    return (
      <div className="space-y-6 pb-12">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  }

  if (!projects || projects.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Human Review Queue"
          description="Audit and resolve detected discrepancies: Accept findings, mark false positives, escalate, or override data."
        />
        <EmptyState
          icon={CheckSquare}
          title="No Projects Available"
          description="Create a project and run cross-checking to populate discrepancies in the human review queue."
          actionLabel="View Projects"
          onAction={() => router.push("/projects")}
        />
      </div>
    );
  }

  // Extract all discrepancies across all match groups for the selected project
  const allDiscrepancies = (crosscheck?.groups || []).flatMap((g) =>
    (g.discrepancies || []).map((d) => ({
      ...d,
      matchGroupSku: g.final_sku || g.canonical_sku || "Unknown SKU",
      matchGroupStatus: g.status,
    }))
  );

  const filteredDiscrepancies = allDiscrepancies.filter((d) => {
    if (severityFilter === "ALL") return true;
    return d.severity.toUpperCase() === severityFilter.toUpperCase();
  });

  const openCount = allDiscrepancies.filter((d) => d.status === "OPEN" || d.status === "ESCALATED").length;
  const criticalCount = allDiscrepancies.filter((d) => d.severity.toUpperCase() === "CRITICAL").length;
  const resolvedCount = allDiscrepancies.filter((d) => d.status !== "OPEN" && d.status !== "ESCALATED").length;

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader
          title="Human Review Queue"
          description="Audit and resolve detected variances: Accept findings, mark false positives, or acknowledge manufacturer changes."
        />
        {activeProject && (
          <Link
            href={`/projects/${activeProject.id}/crosscheck`}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-[#0EA5E9] hover:bg-[#0284C7] text-white shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/50 shrink-0"
          >
            <span>CrossCheck Workspace</span>
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>

      {/* Project Selector */}
      <div className="space-y-2">
        <label className="text-xs font-bold text-[#58708F] uppercase tracking-wider">
          Active Project
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {projects.map((proj) => {
            const isSelected = proj.id === activeProjectId;
            return (
              <button
                key={proj.id}
                type="button"
                onClick={() => setSelectedProjectId(proj.id)}
                className={`flex flex-col text-left p-3.5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? "bg-white border-[#0EA5E9] ring-2 ring-[#0EA5E9]/20 shadow-sm"
                    : "bg-white/60 hover:bg-white border-[#E2E8F0] hover:border-[#CBD5E1]"
                }`}
              >
                <div className="flex items-center justify-between gap-2 w-full">
                  <div className="flex items-center gap-2 truncate">
                    <FolderKanban className={`h-4 w-4 shrink-0 ${isSelected ? "text-[#0EA5E9]" : "text-[#58708F]"}`} />
                    <span className="font-semibold text-sm text-[#0F2747] truncate">
                      {proj.name}
                    </span>
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                    {proj.status.replace("_", " ")}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Review Metrics Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600 shrink-0">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xl font-bold text-[#0F2747]">{openCount}</div>
            <div className="text-xs font-semibold text-[#58708F]">Pending Review Items</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 shrink-0">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xl font-bold text-[#0F2747]">{criticalCount}</div>
            <div className="text-xs font-semibold text-[#58708F]">Critical Discrepancies</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 shrink-0">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xl font-bold text-[#0F2747]">{resolvedCount}</div>
            <div className="text-xs font-semibold text-[#58708F]">Resolved / Audited</div>
          </div>
        </div>
      </div>

      {/* Severity Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-[#E2E8F0] pb-3">
        {["ALL", "CRITICAL", "WARNING", "INFO"].map((sev) => (
          <button
            key={sev}
            type="button"
            onClick={() => setSeverityFilter(sev)}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-colors cursor-pointer ${
              severityFilter === sev
                ? "bg-[#0F2747] text-white"
                : "bg-white text-[#58708F] hover:text-[#0F2747] border border-[#E2E8F0]"
            }`}
          >
            {sev === "ALL" ? `All Items (${allDiscrepancies.length})` : sev}
          </button>
        ))}
      </div>

      {/* Discrepancy Queue List */}
      {isCrossCheckLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
      ) : filteredDiscrepancies.length > 0 ? (
        <div className="space-y-3">
          {filteredDiscrepancies.map((d) => {
            const isProcessing = processingDiscrepancyId === d.id;
            const isCritical = d.severity.toUpperCase() === "CRITICAL";
            const isWarning = d.severity.toUpperCase() === "WARNING";
            const isResolved = d.status !== "OPEN" && d.status !== "ESCALATED";

            return (
              <div
                key={d.id}
                className="bg-white rounded-xl border border-[#E2E8F0] p-5 shadow-sm hover:shadow-md transition-shadow space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    {isCritical ? (
                      <span className="p-1.5 rounded-lg bg-rose-50 text-rose-600 border border-rose-200">
                        <AlertOctagon className="h-4 w-4" />
                      </span>
                    ) : isWarning ? (
                      <span className="p-1.5 rounded-lg bg-amber-50 text-amber-600 border border-amber-200">
                        <AlertTriangle className="h-4 w-4" />
                      </span>
                    ) : (
                      <span className="p-1.5 rounded-lg bg-blue-50 text-blue-600 border border-blue-200">
                        <Info className="h-4 w-4" />
                      </span>
                    )}
                    <div>
                      <h4 className="text-sm font-bold text-[#0F2747]">
                        SKU: <span className="font-mono text-[#0EA5E9]">{d.matchGroupSku}</span> — Field: <span className="capitalize">{d.field_name.replace("_", " ")}</span>
                      </h4>
                      <p className="text-xs text-[#58708F] mt-0.5">
                        {d.explanation || "Detected variance during automated 3-way reconciliation."}
                      </p>
                    </div>
                  </div>

                  <span
                    className={`text-[10px] font-bold px-2.5 py-1 rounded-full uppercase tracking-wider self-start sm:self-auto ${
                      isResolved
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}
                  >
                    Status: {d.status}
                  </span>
                </div>

                {/* Values Comparison Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 p-3 rounded-lg bg-slate-50 border border-slate-200/60 text-xs">
                  <div>
                    <span className="text-[10px] font-bold text-[#58708F] uppercase block mb-1">Design Drawing</span>
                    <span className="font-mono text-[#0F2747] font-semibold block break-words">
                      {formatDisplayValue(d.design_value)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-[#58708F] uppercase block mb-1">Purchase Order</span>
                    <span className="font-mono text-[#0F2747] font-semibold block break-words">
                      {formatDisplayValue(d.order_value)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-[#58708F] uppercase block mb-1">Ack Confirmation</span>
                    <span className="font-mono text-[#0F2747] font-semibold block break-words">
                      {formatDisplayValue(d.ack_value)}
                    </span>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-slate-100">
                  <button
                    type="button"
                    disabled={isProcessing}
                    onClick={() => reviewMutation.mutate({ discrepancyId: d.id, action: "ACCEPT_FINDING" })}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Accept Finding
                  </button>

                  <button
                    type="button"
                    disabled={isProcessing}
                    onClick={() => reviewMutation.mutate({ discrepancyId: d.id, action: "FALSE_POSITIVE" })}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    Mark False Positive
                  </button>

                  <button
                    type="button"
                    disabled={isProcessing}
                    onClick={() => reviewMutation.mutate({ discrepancyId: d.id, action: "ACKNOWLEDGE_MFR_CHANGE" })}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    <FileCheck2 className="h-3.5 w-3.5" />
                    Acknowledge Mfr Change
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-[#E2E8F0] p-8 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-emerald-50 border border-emerald-100 flex items-center justify-center mx-auto text-emerald-600">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <h3 className="text-base font-bold text-[#0F2747]">All Reviews Cleared for {activeProject?.name}</h3>
          <p className="text-xs text-[#58708F] max-w-sm mx-auto">
            No discrepancies match the selected filter or require additional auditor intervention.
          </p>
        </div>
      )}
    </div>
  );
}


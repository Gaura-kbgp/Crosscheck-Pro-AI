"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { useProjects } from "@/lib/hooks/use-projects";
import { useCrossCheck } from "@/lib/hooks/use-crosscheck";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/feedback/empty-state";
import { CrossCheckSummary } from "@/components/crosscheck/crosscheck-summary";
import { CrossCheckList } from "@/components/crosscheck/crosscheck-list";
import { MatchGroupDetailDrawer } from "@/components/crosscheck/match-group-detail-drawer";
import { 
  GitCompare, 
  ArrowRight, 
  FileCheck2, 
  AlertTriangle, 
  Layers, 
  FolderKanban,
  CheckCircle2
} from "lucide-react";

export default function CrossCheckHubPage() {
  const router = useRouter();
  const { data: projects, isLoading: isProjectsLoading } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);

  // Default to the first processed project or first project if none selected
  const activeProjectId = selectedProjectId || (projects && projects.length > 0 ? projects[0].id : null);
  const activeProject = projects?.find((p) => p.id === activeProjectId) || null;

  const {
    data: crosscheck,
    isLoading: isCrossCheckLoading,
    refetch: refetchCrossCheck,
  } = useCrossCheck(activeProjectId || undefined);

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
          title="Three-Way CrossCheck"
          description="Side-by-side reconciliation of SKUs, quantities, dimensions, finishes, and door styles."
        />
        <EmptyState
          icon={GitCompare}
          title="No Projects Available"
          description="Create a project and upload your Design, Purchase Order, and Acknowledgement documents to perform automated cross-checking."
          actionLabel="Create Project"
          onAction={() => router.push("/projects")}
        />
      </div>
    );
  }

  const selectedGroup = crosscheck?.groups.find((g) => g.id === selectedGroupId) || null;

  return (
    <div className="space-y-6 pb-12 relative">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader
          title="Three-Way CrossCheck Hub"
          description="Audit side-by-side matches, missing components, and dimension variances across all projects."
        />
        {activeProject && (
          <Link
            href={`/projects/${activeProject.id}/crosscheck`}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-[#0EA5E9] hover:bg-[#0284C7] text-white shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/50 shrink-0"
          >
            <span>Full Workspace View</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>

      {/* Project Selector Tabs / Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-[#58708F] uppercase tracking-wider">
            Select Active Project
          </label>
          <span className="text-xs text-[#58708F]">
            {projects.length} project{projects.length === 1 ? "" : "s"} total
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {projects.map((proj) => {
            const isSelected = proj.id === activeProjectId;
            const isProcessed = proj.status === "COMPLETED" || proj.status === "REVIEW_REQUIRED" || proj.status === "FINALIZED";

            return (
              <button
                key={proj.id}
                type="button"
                onClick={() => setSelectedProjectId(proj.id)}
                className={`flex flex-col text-left p-4 rounded-xl border transition-all ${
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
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      proj.status === "COMPLETED" || proj.status === "FINALIZED"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : proj.status === "REVIEW_REQUIRED"
                        ? "bg-amber-50 text-amber-700 border border-amber-200"
                        : proj.status === "PROCESSING"
                        ? "bg-blue-50 text-blue-700 border border-blue-200 animate-pulse"
                        : "bg-slate-50 text-slate-600 border border-slate-200"
                    }`}
                  >
                    {proj.status.replace("_", " ")}
                  </span>
                </div>
                <div className="mt-2.5 flex items-center gap-4 text-xs text-[#58708F]">
                  <span>Customer: <strong className="text-[#0F2747] font-medium">{proj.customer_name || "General"}</strong></span>
                  <span>•</span>
                  <span>Dealer: <strong className="text-[#0F2747] font-medium">{proj.dealer_name || "Direct"}</strong></span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Selected Project CrossCheck Results View */}
      {isCrossCheckLoading ? (
        <div className="space-y-4 pt-4">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
      ) : crosscheck && crosscheck.groups.length > 0 ? (
        <div className="space-y-6 pt-2">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-[#0F2747] flex items-center gap-2">
              <Layers className="h-4 w-4 text-[#0EA5E9]" />
              Reconciliation for {activeProject?.name}
            </h2>
            <Link
              href={`/projects/${activeProject?.id}`}
              className="text-xs font-semibold text-[#58708F] hover:text-[#0F2747] transition-colors"
            >
              Project Details ↗
            </Link>
          </div>

          <CrossCheckSummary summary={crosscheck.summary} />

          <CrossCheckList
            groups={crosscheck.groups}
            onSelectGroup={(id) => setSelectedGroupId(id)}
          />

          <MatchGroupDetailDrawer
            group={selectedGroup}
            isOpen={!!selectedGroup}
            onClose={() => setSelectedGroupId(null)}
          />
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-[#E2E8F0] p-8 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-blue-50 border border-blue-100 flex items-center justify-center mx-auto text-[#0EA5E9]">
            <GitCompare className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-[#0F2747]">
              No Cross-Check Data for {activeProject?.name}
            </h3>
            <p className="text-xs text-[#58708F] mt-1 max-w-md mx-auto">
              This project hasn&apos;t been cross-checked yet. Upload the Design, PO, and Acknowledgement documents, then run processing.
            </p>
          </div>
          {activeProject && (
            <Link
              href={`/projects/${activeProject.id}`}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-[#0EA5E9] hover:bg-[#0284C7] text-white transition-colors"
            >
              Go to Project Workspace
            </Link>
          )}
        </div>
      )}
    </div>
  );
}


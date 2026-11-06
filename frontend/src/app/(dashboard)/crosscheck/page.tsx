"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { useProjects } from "@/lib/hooks/use-projects";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/feedback/empty-state";
import { GitCompare, FolderKanban } from "lucide-react";

/**
 * Picks which project's Cross-Check Results to open — this used to also
 * render a full duplicate preview of that project's matrix inline, with a
 * separate "Full Workspace View" button to the real per-project page.
 * Nobody needs two renderings of the same data: picking a project now
 * goes straight there.
 */
export default function CrossCheckProjectPickerPage() {
  const router = useRouter();
  const { data: projects, isLoading: isProjectsLoading } = useProjects();

  if (isProjectsLoading) {
    return (
      <div className="space-y-6 pb-12">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
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
          description="Create a project and upload your Design, Cabinet List, and Acknowledgement documents to perform automated cross-checking."
          actionLabel="Create Project"
          onAction={() => router.push("/projects")}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      <PageHeader
        title="Three-Way CrossCheck"
        description="Pick a project to see its Design / Cabinet List / Acknowledgement reconciliation."
      />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-[#58708F] uppercase tracking-wider">
            Select a Project
          </label>
          <span className="text-xs text-[#58708F]">
            {projects.length} project{projects.length === 1 ? "" : "s"} total
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {projects.map((proj) => (
            <button
              key={proj.id}
              type="button"
              onClick={() => router.push(`/projects/${proj.id}/crosscheck`)}
              className="flex flex-col text-left p-4 rounded-xl border bg-white/60 hover:bg-white border-[#E2E8F0] hover:border-[#0EA5E9] hover:shadow-sm transition-all"
            >
              <div className="flex items-center justify-between gap-2 w-full">
                <div className="flex items-center gap-2 truncate">
                  <FolderKanban className="h-4 w-4 shrink-0 text-[#58708F]" />
                  <span className="font-semibold text-sm text-[#0F2747] truncate">
                    {proj.name}
                  </span>
                </div>
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold shrink-0 ${
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
          ))}
        </div>
      </div>
    </div>
  );
}

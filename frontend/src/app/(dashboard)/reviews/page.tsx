"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { useProjects } from "@/lib/hooks/use-projects";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/feedback/empty-state";
import { CheckSquare, FolderKanban } from "lucide-react";

/**
 * Picks which project's Human Review queue to open. This used to also
 * render a second, independent review-actions implementation inline
 * (its own Accept/False Positive/Ack Mfr Change buttons, bypassing the
 * reason-required-on-override and escalate/finalize-gating logic the
 * real per-project Review page has) — nobody needs two different ways to
 * review the same findings. Picking a project now goes straight there.
 */
export default function ReviewsProjectPickerPage() {
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
          title="Human Review"
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

  return (
    <div className="space-y-6 pb-12">
      <PageHeader
        title="Human Review"
        description="Pick a project to review its discrepancies: accept, reject, override, or escalate."
      />

      <div className="space-y-2">
        <label className="text-xs font-bold text-[#58708F] uppercase tracking-wider">
          Select a Project
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {projects.map((proj) => (
            <button
              key={proj.id}
              type="button"
              onClick={() => router.push(`/projects/${proj.id}/review`)}
              className="flex flex-col text-left p-3.5 rounded-xl border bg-white/60 hover:bg-white border-[#E2E8F0] hover:border-[#0EA5E9] hover:shadow-sm transition-all cursor-pointer"
            >
              <div className="flex items-center justify-between gap-2 w-full">
                <div className="flex items-center gap-2 truncate">
                  <FolderKanban className="h-4 w-4 shrink-0 text-[#58708F]" />
                  <span className="font-semibold text-sm text-[#0F2747] truncate">
                    {proj.name}
                  </span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 shrink-0">
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

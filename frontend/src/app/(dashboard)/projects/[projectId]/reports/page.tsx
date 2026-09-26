"use client";

import React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useProject } from "@/lib/hooks/use-projects";
import { ReportSummary } from "@/components/reports/report-summary";
import { ReportHistoryList } from "@/components/reports/report-history-list";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import { ProjectStatusBadge } from "@/components/badges/status-badge";
import { ErrorState } from "@/components/feedback/error-state";
import { Button } from "@/components/ui/button";

export default function ReportsPage() {
  const params = useParams();
  const projectId = (params?.projectId as string) || "";

  const { data: project, isLoading: isProjectLoading, error: projectError, refetch: refetchProject } = useProject(projectId);

  if (isProjectLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#0EA5E9]" />
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <div className="space-y-6 pb-12">
        <Link
          href={`/projects/${projectId}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#58708F] hover:text-[#0F2747]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Project Details
        </Link>
        <ErrorState
          title="Project not found"
          message="Could not load details for this project."
          onRetry={refetchProject}
        />
      </div>
    );
  }

  // Reports should primarily be generated on REVIEW_REQUIRED, COMPLETED, or FINALIZED
  const canGenerateReports = ["REVIEW_REQUIRED", "COMPLETED", "FINALIZED"].includes(project.status);

  return (
    <div className="space-y-6 pb-12 max-w-6xl mx-auto">
      {/* Header */}
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#58708F] hover:text-[#0F2747] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/30 rounded-md py-1 px-1.5 -ml-1.5 mb-4"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Project</span>
        </Link>
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[#0F2747] tracking-tight">
                Project Reports
              </h1>
              <ProjectStatusBadge status={project.status} />
            </div>
            <p className="text-sm text-[#58708F]">
              Generate, download, and manage reports for {project.name}.
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}/crosscheck`}>
              <Button variant="outline" size="sm">
                View Cross-Check Matrix
              </Button>
            </Link>
            <Link href={`/projects/${projectId}/review`}>
              <Button variant="outline" size="sm">
                View Reviews
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {!canGenerateReports && (
        <div className="flex items-start gap-2.5 rounded-lg border border-[#FDE68A] bg-[#FEF3C7] p-4 text-sm text-[#D97706]">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <div>
            <span className="font-semibold block mb-1">Reports Not Available Yet</span>
            <p>
              Reports and CSV exports are only available once the project has finished processing and cross-checking. 
              Current status is {project.status}.
            </p>
          </div>
        </div>
      )}

      {canGenerateReports && (
        <>
          {/* Summary and Generation Actions */}
          <ReportSummary projectId={projectId} />

          {/* History List */}
          <ReportHistoryList projectId={projectId} />
        </>
      )}
    </div>
  );
}

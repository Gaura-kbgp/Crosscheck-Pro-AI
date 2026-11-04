"use client";

import React from "react";
import Link from "next/link";
import { Project } from "@/lib/api/types";
import { ProjectStatusBadge } from "@/components/badges/status-badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import { ArrowLeft, Building, User, Play, ClipboardCheck, Table2, FileText, RotateCcw } from "lucide-react";
import { ProjectWorkflowStepper } from "./project-workflow-stepper";

interface ProjectDetailHeaderProps {
  project: Project;
  canProcess: boolean;
  isAllUploaded: boolean;
  isProcessing: boolean;
  onStartCrossCheck?: () => void;
  onRescan?: () => void;
  canEdit?: boolean;
}

export function ProjectDetailHeader({
  project,
  canProcess,
  isAllUploaded,
  isProcessing,
  onStartCrossCheck,
  onRescan,
}: ProjectDetailHeaderProps) {
  return (
    <div className="space-y-4">
      {/* Breadcrumb Back link */}
      <div>
        <Link
          href="/projects"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#58708F] hover:text-[#0F2747] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/30 rounded-md py-1 px-1.5 -ml-1.5"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Projects</span>
        </Link>
      </div>

      {/* Where this project is in its lifecycle, start to finish */}
      <div className="rounded-xl border border-[#DCE6F0] bg-white px-5 py-4 shadow-2xs">
        <ProjectWorkflowStepper status={project.status} isAllUploaded={isAllUploaded} />
      </div>

      {/* Main Header Container */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 rounded-xl border border-[#DCE6F0] bg-white p-5 sm:p-6 shadow-2xs">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl sm:text-2xl font-bold text-[#0F2747] tracking-tight">
              {project.name}
            </h1>
            <ProjectStatusBadge status={project.status} />
          </div>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-[#58708F]">
            {project.customer_name && (
              <span className="flex items-center gap-1.5 font-medium text-[#0F2747]">
                <User className="h-3.5 w-3.5 text-[#58708F]" />
                <span>Customer: {project.customer_name}</span>
              </span>
            )}
            {project.dealer_name && (
              <span className="flex items-center gap-1.5 font-medium text-[#0F2747]">
                <Building className="h-3.5 w-3.5 text-[#58708F]" />
                <span>Dealer: {project.dealer_name}</span>
              </span>
            )}
            <span>Updated {formatDate(project.updated_at || project.created_at)}</span>
          </div>
        </div>

        {/* Primary CTA Area — the ONE colored button is always the
            recommended next action for this status (matches the stepper
            above); everything else is outline/secondary, and sits after
            it so reading order matches priority order. */}
        <div className="flex flex-wrap items-center gap-3 shrink-0">
          {project.status === "COMPLETED" || project.status === "REVIEW_REQUIRED" || project.status === "FINALIZED" ? (
            <>
              {project.status === "REVIEW_REQUIRED" && (
                <Link href={`/projects/${project.id}/review`}>
                  <Button
                    variant="default"
                    size="default"
                    className="bg-[#16A34A] hover:bg-[#15803D] text-white"
                    leftIcon={<ClipboardCheck className="h-4 w-4" />}
                  >
                    Human Review
                  </Button>
                </Link>
              )}

              {project.status === "COMPLETED" && (
                <Link href={`/projects/${project.id}/crosscheck`}>
                  <Button
                    variant="default"
                    size="default"
                    className="bg-[#16A34A] hover:bg-[#15803D] text-white"
                    leftIcon={<Table2 className="h-4 w-4" />}
                  >
                    View Cross-Check Matrix
                  </Button>
                </Link>
              )}

              {project.status === "FINALIZED" && (
                <Link href={`/projects/${project.id}/reports`}>
                  <Button
                    variant="default"
                    size="default"
                    className="bg-[#16A34A] hover:bg-[#15803D] text-white"
                    leftIcon={<FileText className="h-4 w-4" />}
                  >
                    Reports
                  </Button>
                </Link>
              )}

              {/* Secondary / supporting actions, always outline so the one
                  colored button above never has to compete for attention. */}
              {project.status !== "REVIEW_REQUIRED" && (
                <Link href={`/projects/${project.id}/review`}>
                  <Button variant="outline" size="default" leftIcon={<ClipboardCheck className="h-4 w-4" />}>
                    {project.status === "FINALIZED" ? "View Review" : "Human Review"}
                  </Button>
                </Link>
              )}
              {project.status !== "COMPLETED" && (
                <Link href={`/projects/${project.id}/crosscheck`}>
                  <Button variant="outline" size="default" leftIcon={<Table2 className="h-4 w-4" />}>
                    View Cross-Check Matrix
                  </Button>
                </Link>
              )}
              {project.status !== "FINALIZED" && (
                <Link href={`/projects/${project.id}/reports`}>
                  <Button variant="outline" size="default" leftIcon={<FileText className="h-4 w-4" />}>
                    Reports
                  </Button>
                </Link>
              )}
              {project.status !== "FINALIZED" && canProcess && (
                <Button
                  variant="outline"
                  size="default"
                  disabled={isProcessing}
                  isLoading={isProcessing}
                  onClick={onRescan}
                  leftIcon={!isProcessing ? <RotateCcw className="h-4 w-4" /> : undefined}
                >
                  Rescan
                </Button>
              )}
            </>
          ) : (
            <Button
              variant="default"
              size="default"
              disabled={!isAllUploaded || isProcessing || !canProcess}
              isLoading={isProcessing}
              onClick={onStartCrossCheck}
              leftIcon={!isProcessing ? <Play className="h-4 w-4 fill-current" /> : undefined}
              className="gap-2 font-semibold"
            >
              {isProcessing ? "Processing Cross-Check..." : "Start Cross-Check"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

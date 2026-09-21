"use client";

import React from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { ProjectStatusBadge } from "@/components/badges/status-badge";
import { Project, Role } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";
import { ProjectActionMenu } from "./project-action-menu";
import {
  FolderKanban,
  ArrowRight,
  CheckCircle2,
  Clock,
  Calendar,
  Layers,
  GitCompare,
  FileCheck2,
  FileText,
  Sparkles,
} from "lucide-react";

interface ProjectCardsListProps {
  projects: Project[];
  userRole?: Role;
  onEdit?: (project: Project) => void;
  onDelete?: (project: Project) => void;
  forceGrid?: boolean;
}

export function ProjectCardsList({
  projects,
  userRole,
  onEdit,
  onDelete,
  forceGrid = false,
}: ProjectCardsListProps) {
  return (
    <div
      className={
        forceGrid
          ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5"
          : "grid grid-cols-1 md:grid-cols-2 gap-4 lg:hidden"
      }
    >
      {projects.map((project) => {
        const uploadedTypes = project.uploaded_document_types || [];
        const hasDesign = uploadedTypes.includes("DESIGN");
        const hasOrder = uploadedTypes.includes("ORDER");
        const hasAck = uploadedTypes.includes("ACKNOWLEDGEMENT");

        const docCount =
          project.document_count !== undefined
            ? project.document_count
            : (hasDesign ? 1 : 0) + (hasOrder ? 1 : 0) + (hasAck ? 1 : 0);

        const progressPct =
          project.progress_percentage !== undefined
            ? project.progress_percentage
            : project.status === "COMPLETED" || project.status === "FINALIZED"
            ? 100
            : project.status === "PROCESSING"
            ? 70
            : docCount === 3
            ? 100
            : docCount === 2
            ? 66
            : docCount === 1
            ? 33
            : 0;

        const docs = [
          { key: "DESIGN", label: "Design Spec", short: "Design", isUploaded: hasDesign },
          { key: "ORDER", label: "Purchase Order", short: "Order", isUploaded: hasOrder },
          { key: "ACKNOWLEDGEMENT", label: "Acknowledgment", short: "Ack", isUploaded: hasAck },
        ];

        const metaParts = [
          project.customer_name ? `Customer: ${project.customer_name}` : null,
          project.dealer_name ? `Dealer: ${project.dealer_name}` : null,
        ].filter(Boolean);

        const hasDiscrepancies = (project.discrepancy_count || 0) > 0;
        const allResolved =
          hasDiscrepancies &&
          project.resolved_discrepancy_count === project.discrepancy_count;

        // Determine Primary Action text & link based on project status & docs
        let primaryActionLabel = "Open Workspace";
        let primaryActionHref = `/projects/${project.id}`;
        let primaryActionIcon = <ArrowRight className="h-4 w-4" />;

        if (project.status === "REVIEW_REQUIRED") {
          primaryActionLabel = "Review Queue";
          primaryActionHref = `/projects/${project.id}/review`;
          primaryActionIcon = <GitCompare className="h-4 w-4" />;
        } else if (docCount === 3 && project.status === "DRAFT") {
          primaryActionLabel = "Run CrossCheck";
          primaryActionHref = `/projects/${project.id}/crosscheck`;
          primaryActionIcon = <Sparkles className="h-4 w-4" />;
        } else if (project.status === "COMPLETED" || project.status === "FINALIZED") {
          primaryActionLabel = "View Report";
          primaryActionHref = `/projects/${project.id}/reports`;
          primaryActionIcon = <FileText className="h-4 w-4" />;
        } else if (docCount < 3) {
          primaryActionLabel = `Upload Docs (${docCount}/3)`;
          primaryActionHref = `/projects/${project.id}`;
          primaryActionIcon = <Layers className="h-4 w-4" />;
        }

        return (
          <Card
            key={project.id}
            className="group/card border border-[#DCE6F0] bg-white hover:border-[#0EA5E9]/50 hover:shadow-md transition-all relative overflow-hidden flex flex-col justify-between rounded-xl"
          >
            <CardContent className="p-5 space-y-4">
              {/* Header: Folder Icon, Project Name, Customer Info, Action Menu */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-50 text-[#0EA5E9] group-hover/card:bg-[#0EA5E9] group-hover/card:text-white transition-colors mt-0.5">
                    <FolderKanban className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <Link
                      href={`/projects/${project.id}`}
                      className="text-base font-bold text-[#0F2747] hover:text-[#0284C7] transition-colors line-clamp-1 leading-snug block"
                    >
                      {project.name}
                    </Link>
                    {metaParts.length > 0 ? (
                      <p className="text-xs text-[#58708F] font-normal truncate mt-0.5">
                        {metaParts.join(" • ")}
                      </p>
                    ) : (
                      <p className="text-xs text-[#58708F]/70 font-normal italic mt-0.5">
                        No customer details
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <ProjectActionMenu
                    project={project}
                    userRole={userRole}
                    onEdit={onEdit}
                    onDelete={onDelete}
                  />
                </div>
              </div>

              {/* Status and Discrepancy Badges */}
              <div className="flex items-center justify-between gap-2 pt-2 border-t border-[#DCE6F0]/80">
                <ProjectStatusBadge status={project.status} />

                {hasDiscrepancies ? (
                  <span
                    className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                      allResolved
                        ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                        : "text-amber-700 bg-amber-50 border-amber-200"
                    }`}
                  >
                    {allResolved
                      ? `All ${project.discrepancy_count} Resolved`
                      : `${project.resolved_discrepancy_count || 0}/${project.discrepancy_count} Reviewed`}
                  </span>
                ) : (
                  <span className="text-[11px] font-medium text-[#58708F] flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {formatDate(project.updated_at || project.created_at)}
                  </span>
                )}
              </div>

              {/* 3-Way Document Checklist Pills */}
              <div className="space-y-1.5 bg-[#F7F9FC] p-3 rounded-lg border border-[#DCE6F0]/80">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[#0F2747] flex items-center gap-1.5">
                    <FileCheck2 className="h-3.5 w-3.5 text-[#0EA5E9]" />
                    3-Way Documents
                  </span>
                  <span className="font-mono text-xs font-bold text-[#0EA5E9]">
                    {docCount} / 3 Uploaded
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-1.5 pt-1">
                  {docs.map((doc) => (
                    <div
                      key={doc.key}
                      className={`flex items-center justify-center gap-1 py-1 px-1.5 rounded text-[11px] font-bold border transition-colors ${
                        doc.isUploaded
                          ? "bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]"
                          : "bg-white text-[#58708F] border-[#DCE6F0]"
                      }`}
                    >
                      {doc.isUploaded ? (
                        <CheckCircle2 className="h-3 w-3 text-[#15803D] shrink-0" />
                      ) : (
                        <Clock className="h-3 w-3 text-[#58708F] shrink-0" />
                      )}
                      <span className="truncate">{doc.short}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Pipeline Progress Bar */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-medium text-[#58708F]">Pipeline Progress</span>
                  <span className="font-bold text-[#0F2747]">{progressPct}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-[#F1F5F9] border border-[#E2E8F0]">
                  <div
                    className={`h-full transition-all duration-300 ${
                      project.status === "FAILED"
                        ? "bg-[#DC2626]"
                        : project.status === "COMPLETED" ||
                          project.status === "FINALIZED"
                        ? "bg-[#16A34A]"
                        : progressPct >= 70
                        ? "bg-[#0EA5E9]"
                        : "bg-[#38BDF8]"
                    }`}
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>

              {/* Quick Launch Direct Action Bar */}
              <div className="pt-2 border-t border-[#DCE6F0] flex items-center justify-between gap-2">
                {/* Module Quick Nav Shortcuts */}
                <div className="flex items-center gap-1 text-xs">
                  <Link
                    href={`/projects/${project.id}`}
                    title="Upload & View Documents"
                    className="p-1.5 rounded-md hover:bg-slate-100 text-[#58708F] hover:text-[#0F2747] transition-colors"
                  >
                    <Layers className="h-4 w-4" />
                  </Link>
                  <Link
                    href={`/projects/${project.id}/crosscheck`}
                    title="Three-Way CrossCheck Matrix"
                    className="p-1.5 rounded-md hover:bg-sky-50 text-[#58708F] hover:text-[#0EA5E9] transition-colors"
                  >
                    <Sparkles className="h-4 w-4" />
                  </Link>
                  <Link
                    href={`/projects/${project.id}/review`}
                    title="Discrepancy Review Queue"
                    className="p-1.5 rounded-md hover:bg-amber-50 text-[#58708F] hover:text-amber-600 transition-colors"
                  >
                    <GitCompare className="h-4 w-4" />
                  </Link>
                  <Link
                    href={`/projects/${project.id}/reports`}
                    title="Reports & Audit Exports"
                    className="p-1.5 rounded-md hover:bg-emerald-50 text-[#58708F] hover:text-emerald-600 transition-colors"
                  >
                    <FileText className="h-4 w-4" />
                  </Link>
                </div>

                {/* Primary CTA Button */}
                <Link
                  href={primaryActionHref}
                  className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#0EA5E9] hover:bg-[#0284C7] text-white text-xs font-bold shadow-2xs transition-all hover:scale-[1.02] active:scale-[0.98]"
                >
                  <span>{primaryActionLabel}</span>
                  {primaryActionIcon}
                </Link>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

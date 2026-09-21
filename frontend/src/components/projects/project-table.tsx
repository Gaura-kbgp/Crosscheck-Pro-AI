"use client";

import React from "react";
import Link from "next/link";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { ProjectStatusBadge } from "@/components/badges/status-badge";
import { Project, Role } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";
import { ProjectActionMenu } from "./project-action-menu";
import {
  FolderKanban,
  ArrowUpRight,
  ArrowRight,
  CheckCircle2,
  Clock,
  Layers,
  Sparkles,
  GitCompare,
  FileText,
} from "lucide-react";

interface ProjectTableProps {
  projects: Project[];
  userRole?: Role;
  onEdit?: (project: Project) => void;
  onDelete?: (project: Project) => void;
}

export function ProjectTable({
  projects,
  userRole,
  onEdit,
  onDelete,
}: ProjectTableProps) {
  return (
    <div className="bg-white rounded-xl border border-[#DCE6F0] shadow-2xs overflow-visible">
      <div className="overflow-x-auto overflow-y-visible">
        <Table>
          <TableHeader>
            <TableRow className="bg-[#F7F9FC] hover:bg-[#F7F9FC] border-b border-[#DCE6F0]">
              <TableHead className="w-[28%] text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                Project
              </TableHead>
              <TableHead className="w-[14%] text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                Status
              </TableHead>
              <TableHead className="w-[18%] text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                3-Way Documents
              </TableHead>
              <TableHead className="w-[15%] text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                Pipeline Progress
              </TableHead>
              <TableHead className="w-[12%] text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                Last Updated
              </TableHead>
              <TableHead className="w-[13%] text-right text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                Quick Actions
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
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
                { key: "DESIGN", label: "Design Spec", short: "D", isUploaded: hasDesign },
                { key: "ORDER", label: "Purchase Order", short: "O", isUploaded: hasOrder },
                { key: "ACKNOWLEDGEMENT", label: "Ack", short: "A", isUploaded: hasAck },
              ];

              const metaParts = [
                project.customer_name ? `Customer: ${project.customer_name}` : null,
                project.dealer_name ? `Dealer: ${project.dealer_name}` : null,
              ].filter(Boolean);

              const hasDiscrepancies = (project.discrepancy_count || 0) > 0;
              const allResolved =
                hasDiscrepancies &&
                project.resolved_discrepancy_count === project.discrepancy_count;

              // Determine Primary Action button for direct click
              let primaryActionLabel = "Open";
              let primaryActionHref = `/projects/${project.id}`;

              if (project.status === "REVIEW_REQUIRED") {
                primaryActionLabel = "Review";
                primaryActionHref = `/projects/${project.id}/review`;
              } else if (docCount === 3 && project.status === "DRAFT") {
                primaryActionLabel = "CrossCheck";
                primaryActionHref = `/projects/${project.id}/crosscheck`;
              } else if (project.status === "COMPLETED" || project.status === "FINALIZED") {
                primaryActionLabel = "Report";
                primaryActionHref = `/projects/${project.id}/reports`;
              }

              return (
                <TableRow
                  key={project.id}
                  className="group hover:bg-[#F7F9FC] transition-colors border-b border-[#DCE6F0]"
                >
                  {/* Project Column */}
                  <TableCell className="py-4">
                    <div className="flex items-start gap-3">
                      <Link
                        href={`/projects/${project.id}`}
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#E0F2FE] text-[#0EA5E9] group-hover:bg-[#0EA5E9] group-hover:text-white transition-colors mt-0.5"
                      >
                        <FolderKanban className="h-4 w-4" />
                      </Link>
                      <div className="flex flex-col space-y-1 min-w-0">
                        <Link
                          href={`/projects/${project.id}`}
                          className="text-[14px] font-bold text-[#0F2747] hover:text-[#0284C7] transition-colors flex items-center gap-1.5 truncate"
                        >
                          {project.name}
                          <ArrowUpRight className="h-3.5 w-3.5 opacity-0 group-hover:opacity-100 text-[#0284C7] transition-opacity shrink-0" />
                        </Link>
                        {metaParts.length > 0 ? (
                          <span className="text-[12px] text-[#58708F] font-normal truncate">
                            {metaParts.join(" • ")}
                          </span>
                        ) : (
                          <span className="text-[12px] text-[#58708F]/70 font-normal italic">
                            No customer details
                          </span>
                        )}

                        {/* Module Quick Nav Shortcuts */}
                        <div className="flex items-center gap-2 pt-0.5 text-[11px] font-semibold text-[#58708F]">
                          <Link
                            href={`/projects/${project.id}`}
                            className="hover:text-[#0EA5E9] transition-colors"
                          >
                            Docs ({docCount}/3)
                          </Link>
                          <span>•</span>
                          <Link
                            href={`/projects/${project.id}/crosscheck`}
                            className="hover:text-[#0EA5E9] transition-colors"
                          >
                            CrossCheck
                          </Link>
                          <span>•</span>
                          <Link
                            href={`/projects/${project.id}/review`}
                            className="hover:text-[#0EA5E9] transition-colors"
                          >
                            Review
                          </Link>
                        </div>
                      </div>
                    </div>
                  </TableCell>

                  {/* Status Column */}
                  <TableCell className="py-4 align-top">
                    <div className="space-y-1 mt-1">
                      <ProjectStatusBadge status={project.status} />
                      {hasDiscrepancies && (
                        <div className="flex items-center gap-1 text-[11px] font-semibold text-[#58708F]">
                          {allResolved ? (
                            <span className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                              All {project.discrepancy_count} Resolved
                            </span>
                          ) : (
                            <span className="text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                              {project.resolved_discrepancy_count || 0}/{project.discrepancy_count} Reviewed
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </TableCell>

                  {/* 3-Way Documents Column */}
                  <TableCell className="py-4 align-top">
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs font-mono font-bold text-[#0F2747] bg-[#F1F5F9] px-2 py-0.5 rounded-md border border-[#DCE6F0]">
                        {docCount} / 3
                      </span>
                      <div className="flex items-center gap-1">
                        {docs.map((doc) => (
                          <span
                            key={doc.key}
                            title={`${doc.label}: ${doc.isUploaded ? "Uploaded & Ready" : "Pending Upload"}`}
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${
                              doc.isUploaded
                                ? "bg-[#DCFCE7] text-[#15803D] border border-[#BBF7D0]"
                                : "bg-[#F7F9FC] text-[#58708F] border border-[#DCE6F0]"
                            }`}
                          >
                            {doc.isUploaded ? (
                              <CheckCircle2 className="h-3 w-3 mr-1 text-[#15803D]" />
                            ) : (
                              <Clock className="h-3 w-3 mr-1 text-[#58708F]" />
                            )}
                            {doc.short}
                          </span>
                        ))}
                      </div>
                    </div>
                  </TableCell>

                  {/* Progress Column */}
                  <TableCell className="py-4 align-top">
                    <div className="space-y-1.5 max-w-[130px] mt-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[12px] font-bold text-[#0F2747]">
                          {progressPct}%
                        </span>
                        <span className="text-[11px] text-[#58708F] font-medium">
                          {progressPct === 100
                            ? "Complete"
                            : docCount === 3
                            ? "Ready"
                            : `${docCount}/3 Docs`}
                        </span>
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
                  </TableCell>

                  {/* Last Updated Column */}
                  <TableCell className="text-[13px] text-[#58708F] font-normal py-4 align-top">
                    <div className="mt-1">
                      {formatDate(project.updated_at || project.created_at)}
                    </div>
                  </TableCell>

                  {/* Quick Actions Column */}
                  <TableCell className="text-right py-4 align-top">
                    <div className="flex items-center justify-end gap-2 mt-0.5">
                      <Link
                        href={primaryActionHref}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0EA5E9] hover:bg-[#0284C7] text-white text-xs font-bold shadow-2xs transition-all hover:scale-[1.02] active:scale-[0.98]"
                      >
                        <span>{primaryActionLabel}</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                      <ProjectActionMenu
                        project={project}
                        userRole={userRole}
                        onEdit={onEdit}
                        onDelete={onDelete}
                      />
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

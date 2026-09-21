"use client";

import React, { useState } from "react";
import { Document, Project } from "@/lib/api/types";
import { DocumentTypeBadge } from "./document-type-badge";
import { DocumentStatusBadge } from "./document-status-badge";
import { formatDate } from "@/lib/utils";
import { documentsApi } from "@/lib/api/endpoints";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  FileText,
  Eye,
  ExternalLink,
  Trash2,
} from "lucide-react";

interface DocumentsTableProps {
  documents: Document[];
  projectsMap: Record<string, Project>;
  onViewDetails: (doc: Document) => void;
  onDeleteDoc?: (doc: Document) => void;
  canManage?: boolean;
}

export function DocumentsTable({
  documents,
  projectsMap,
  onViewDetails,
  onDeleteDoc,
  canManage = true,
}: DocumentsTableProps) {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const formatFileSize = (bytes?: number) => {
    if (!bytes || bytes === 0) return "PDF";
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const handleQuickDownload = async (doc: Document) => {
    try {
      setDownloadingId(doc.id);
      const res = await documentsApi.getUrl(doc.project_id, doc.id);
      if (res?.url) {
        window.open(res.url, "_blank", "noopener,noreferrer");
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Unable to retrieve document download link.");
    } finally {
      setDownloadingId(null);
    }
  };

  if (documents.length === 0) return null;

  return (
    <>
      {/* Desktop Table View (Hidden on mobile) */}
      <div className="hidden md:block overflow-hidden rounded-xl border border-[#DCE6F0] bg-white shadow-2xs">
        <Table>
          <TableHeader className="bg-[#F7F9FC]">
            <TableRow>
              <TableHead className="w-[300px]">Document</TableHead>
              <TableHead>Project</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>File Size</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Uploaded</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((doc) => {
              const project = projectsMap[doc.project_id];
              const filename = doc.original_filename || doc.filename || "Document.pdf";
              const isDownloading = downloadingId === doc.id;

              return (
                <TableRow
                  key={doc.id}
                  className="group hover:bg-[#F7F9FC]/80 transition-colors"
                >
                  {/* Document Name */}
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#E0F2FE] text-[#0EA5E9] group-hover:bg-[#0EA5E9] group-hover:text-white transition-colors">
                        <FileText className="h-4.5 w-4.5" />
                      </div>
                      <div className="min-w-0">
                        <button
                          type="button"
                          onClick={() => onViewDetails(doc)}
                          className="text-xs font-bold text-[#0F2747] hover:text-[#0EA5E9] hover:underline text-left truncate block max-w-[240px]"
                          title={filename}
                        >
                          {filename}
                        </button>
                        <span className="text-[11px] text-[#58708F] block">
                          PDF Document
                        </span>
                      </div>
                    </div>
                  </TableCell>

                  {/* Project */}
                  <TableCell>
                    <span className="text-xs font-semibold text-[#0F2747]">
                      {project?.name || "Project"}
                    </span>
                  </TableCell>

                  {/* Document Type Badge */}
                  <TableCell>
                    <DocumentTypeBadge type={doc.document_type} />
                  </TableCell>

                  {/* File Size */}
                  <TableCell className="text-xs text-[#58708F]">
                    {formatFileSize(doc.file_size)}
                  </TableCell>

                  {/* Status Badge */}
                  <TableCell>
                    <DocumentStatusBadge status={doc.status} />
                  </TableCell>

                  {/* Upload Date */}
                  <TableCell className="text-xs text-[#58708F] whitespace-nowrap">
                    {formatDate(doc.created_at)}
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onViewDetails(doc)}
                        className="h-7 text-xs px-2.5"
                      >
                        <Eye className="h-3.5 w-3.5 mr-1" />
                        Details
                      </Button>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleQuickDownload(doc)}
                        isLoading={isDownloading}
                        className="h-7 text-xs px-2 text-[#0EA5E9] border-[#BAE6FD] hover:bg-[#E0F2FE]"
                        title="View / Download Document"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </Button>

                      {canManage && onDeleteDoc && (
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => onDeleteDoc(doc)}
                          className="h-7 text-xs px-2"
                          title="Delete Document"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Mobile Card List View (Visible on small screens) */}
      <div className="grid grid-cols-1 gap-3 md:hidden">
        {documents.map((doc) => {
          const project = projectsMap[doc.project_id];
          const filename = doc.original_filename || doc.filename || "Document.pdf";
          const isDownloading = downloadingId === doc.id;

          return (
            <div
              key={doc.id}
              className="rounded-xl border border-[#DCE6F0] bg-white p-4 shadow-2xs space-y-3"
            >
              {/* Card Header */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#E0F2FE] text-[#0EA5E9]">
                    <FileText className="h-4.5 w-4.5" />
                  </div>
                  <div className="min-w-0">
                    <h4
                      onClick={() => onViewDetails(doc)}
                      className="text-xs font-bold text-[#0F2747] truncate cursor-pointer hover:underline"
                    >
                      {filename}
                    </h4>
                    <p className="text-[11px] font-medium text-[#58708F]">
                      {project?.name || "Project"}
                    </p>
                  </div>
                </div>

                <DocumentTypeBadge type={doc.document_type} />
              </div>

              {/* Card Details */}
              <div className="flex items-center justify-between text-[11px] text-[#58708F] pt-1 border-t border-[#DCE6F0]/60">
                <span>{formatFileSize(doc.file_size)}</span>
                <span>Uploaded {formatDate(doc.created_at)}</span>
              </div>

              {/* Card Footer: Status & Actions */}
              <div className="flex items-center justify-between pt-1">
                <DocumentStatusBadge status={doc.status} />

                <div className="flex items-center gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onViewDetails(doc)}
                    className="h-7 text-xs px-2.5"
                  >
                    Details
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleQuickDownload(doc)}
                    isLoading={isDownloading}
                    className="h-7 text-xs px-2 text-[#0EA5E9] border-[#BAE6FD]"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                  {canManage && onDeleteDoc && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => onDeleteDoc(doc)}
                      className="h-7 text-xs px-2"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

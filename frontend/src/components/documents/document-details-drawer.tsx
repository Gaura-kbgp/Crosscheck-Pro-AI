"use client";

import React, { useState } from "react";
import { Document, Project } from "@/lib/api/types";
import { documentsApi } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/utils";
import { DocumentTypeBadge } from "./document-type-badge";
import { DocumentStatusBadge } from "./document-status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  FileText,
  ExternalLink,
  Trash2,
  RefreshCw,
  Folder,
  Calendar,
  HardDrive,
  AlertTriangle,
} from "lucide-react";

interface DocumentDetailsDrawerProps {
  open: boolean;
  document: Document | null;
  project?: Project | null;
  onOpenChange: (open: boolean) => void;
  onDelete?: (documentId: string) => Promise<void>;
  onReprocess?: (projectId: string) => Promise<void>;
  canManage?: boolean;
}

export function DocumentDetailsDrawer({
  open,
  document,
  project,
  onOpenChange,
  onDelete,
  onReprocess,
  canManage = true,
}: DocumentDetailsDrawerProps) {
  const [isViewing, setIsViewing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isReprocessing, setIsReprocessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!document) return null;

  const formatFileSize = (bytes?: number) => {
    if (!bytes || bytes === 0) return "PDF document";
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const handleDownloadView = async () => {
    try {
      setIsViewing(true);
      setError(null);
      const res = await documentsApi.getUrl(document.project_id, document.id);
      if (res?.url) {
        window.open(res.url, "_blank", "noopener,noreferrer");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to generate download URL.");
    } finally {
      setIsViewing(false);
    }
  };

  const handleReprocess = async () => {
    if (!onReprocess) return;
    try {
      setIsReprocessing(true);
      setError(null);
      await onReprocess(document.project_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start reprocessing.");
    } finally {
      setIsReprocessing(false);
    }
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    if (!confirm(`Are you sure you want to delete ${document.original_filename}?`)) return;
    try {
      setIsDeleting(true);
      setError(null);
      await onDelete(document.id);
      onOpenChange(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete document.");
    } finally {
      setIsDeleting(false);
    }
  };

  const filename = document.original_filename || document.filename || "Document.pdf";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogClose onClose={() => onOpenChange(false)} />
      <DialogHeader>
        <div className="flex items-center gap-2 mb-1">
          <DocumentTypeBadge type={document.document_type} />
          <DocumentStatusBadge status={document.status} />
        </div>
        <DialogTitle className="text-base font-bold text-[#0F2747] break-all">
          {filename}
        </DialogTitle>
        <DialogDescription>
          Document details and metadata for CrossCheck workflow.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4 py-2">
        {error && (
          <div className="rounded-lg border border-[#FECACA] bg-[#FEE2E2] p-3 text-xs text-[#B91C1C]">
            {error}
          </div>
        )}

        {document.status === "FAILED" && (
          <div className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] p-3.5 space-y-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-[#B91C1C]">
              <AlertTriangle className="h-4 w-4" />
              <span>Document Processing Failed</span>
            </div>
            <p className="text-xs text-[#991B1B]">
              We couldn&apos;t process this document during automatic extraction. Please try reprocessing or re-uploading a clear PDF.
            </p>
            {onReprocess && canManage && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleReprocess}
                isLoading={isReprocessing}
                leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
                className="mt-1 text-xs border-[#FECACA] text-[#B91C1C] hover:bg-[#FEE2E2]"
              >
                Retry Processing
              </Button>
            )}
          </div>
        )}

        <div className="rounded-xl border border-[#DCE6F0] bg-[#F7F9FC] p-4 divide-y divide-[#DCE6F0]/60 space-y-3">
          <div className="flex items-center justify-between text-xs pb-3">
            <span className="flex items-center gap-1.5 text-[#58708F] font-medium">
              <Folder className="h-3.5 w-3.5" /> Project
            </span>
            <span className="font-semibold text-[#0F2747]">
              {project?.name || "Project Document"}
            </span>
          </div>

          <div className="flex items-center justify-between text-xs py-3">
            <span className="flex items-center gap-1.5 text-[#58708F] font-medium">
              <FileText className="h-3.5 w-3.5" /> Type
            </span>
            <span className="font-semibold text-[#0F2747]">
              {document.document_type}
            </span>
          </div>

          <div className="flex items-center justify-between text-xs py-3">
            <span className="flex items-center gap-1.5 text-[#58708F] font-medium">
              <HardDrive className="h-3.5 w-3.5" /> File Size
            </span>
            <span className="font-semibold text-[#0F2747]">
              {formatFileSize(document.file_size)}
            </span>
          </div>

          <div className="flex items-center justify-between text-xs pt-3">
            <span className="flex items-center gap-1.5 text-[#58708F] font-medium">
              <Calendar className="h-3.5 w-3.5" /> Upload Date
            </span>
            <span className="font-semibold text-[#0F2747]">
              {formatDate(document.created_at)}
            </span>
          </div>
        </div>
      </div>

      <DialogFooter className="gap-2 sm:gap-0">
        <div className="flex items-center gap-2 w-full justify-between">
          <div>
            {canManage && onDelete && (
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={handleDelete}
                isLoading={isDeleting}
                leftIcon={<Trash2 className="h-3.5 w-3.5" />}
              >
                Delete
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              Close
            </Button>
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={handleDownloadView}
              isLoading={isViewing}
              leftIcon={<ExternalLink className="h-3.5 w-3.5" />}
            >
              View Document
            </Button>
          </div>
        </div>
      </DialogFooter>
    </Dialog>
  );
}

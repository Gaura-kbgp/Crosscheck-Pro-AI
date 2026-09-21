"use client";

import React, { useState, useRef } from "react";
import { Document, DocumentType } from "@/lib/api/types";
import { DocumentUploadZone } from "./document-upload-zone";
import { RemoveDocumentDialog } from "./remove-document-dialog";
import { documentsApi } from "@/lib/api/endpoints";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import {
  FileText,
  Compass,
  ShoppingCart,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Trash2,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface DocumentTypeConfig {
  type: DocumentType;
  title: string;
  subtitle: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const DOCUMENT_TYPE_CONFIGS: Record<DocumentType, DocumentTypeConfig> = {
  DESIGN: {
    type: "DESIGN",
    title: "Design Document",
    subtitle: "Architectural & CAD Specification",
    description: "Upload the 2020 Design CAD or manufacturer design PDF containing layout specifications and item codes.",
    icon: Compass,
  },
  ORDER: {
    type: "ORDER",
    title: "Purchase Order",
    subtitle: "Client / Dealer Purchase Order",
    description: "Upload the dealer purchase order contract with requested quantities, finishes, styles, and unit pricing.",
    icon: ShoppingCart,
  },
  ACKNOWLEDGEMENT: {
    type: "ACKNOWLEDGEMENT",
    title: "Manufacturer Acknowledgement",
    subtitle: "Factory Order Confirmation",
    description: "Upload the final factory order acknowledgement detailing confirmed production line items and modifications.",
    icon: CheckCircle2,
  },
};

interface ProjectDocumentCardProps {
  documentType: DocumentType;
  projectId: string;
  document?: Document | null;
  onUpload: (type: DocumentType, file: File) => Promise<void>;
  onDelete: (documentId: string) => Promise<void>;
  isUploading?: boolean;
  isDeleting?: boolean;
  canManage?: boolean;
}

export function ProjectDocumentCard({
  documentType,
  projectId,
  document,
  onUpload,
  onDelete,
  isUploading = false,
  isDeleting = false,
  canManage = true,
}: ProjectDocumentCardProps) {
  const config = DOCUMENT_TYPE_CONFIGS[documentType];
  const Icon = config.icon;
  const isUploaded = Boolean(document);
  const [isRemoveDialogOpen, setIsRemoveDialogOpen] = useState(false);
  const [isViewing, setIsViewing] = useState(false);
  const replaceInputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes?: number) => {
    if (!bytes || bytes === 0) return "PDF document";
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const handleView = async () => {
    if (!document) return;
    try {
      setIsViewing(true);
      const res = await documentsApi.getUrl(projectId, document.id);
      if (res?.url) {
        window.open(res.url, "_blank", "noopener,noreferrer");
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Unable to retrieve document link.");
    } finally {
      setIsViewing(false);
    }
  };

  const handleReplaceClick = () => {
    if (!canManage || isUploading) return;
    replaceInputRef.current?.click();
  };

  const handleReplaceFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      await onUpload(documentType, file);
      e.target.value = "";
    }
  };

  const filename =
    document?.original_filename || document?.filename || `${config.title}.pdf`;

  return (
    <>
      <div className="flex flex-col h-full rounded-xl border border-[#DCE6F0] bg-white p-5 shadow-2xs transition-all hover:border-[#0EA5E9]/30">
        {/* Card Header */}
        <div className="flex items-start justify-between gap-3 pb-3 border-b border-[#DCE6F0]">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                isUploaded
                  ? "bg-[#DCFCE7] text-[#16A34A]"
                  : "bg-[#E0F2FE] text-[#0EA5E9]"
              )}
            >
              <Icon className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-[#0F2747] leading-tight">
                  {config.title}
                </h3>
              </div>
              <span className="text-[11px] font-medium text-[#58708F]">
                {config.subtitle}
              </span>
            </div>
          </div>

          <div className="shrink-0">
            {isUploaded ? (
              <Badge variant="success" className="gap-1 font-semibold">
                <Check className="h-3 w-3" />
                <span>Uploaded</span>
              </Badge>
            ) : (
              <Badge variant="secondary" className="font-semibold text-[#58708F]">
                Required
              </Badge>
            )}
          </div>
        </div>

        {/* Card Body */}
        <div className="flex-1 py-4">
          {isUploaded ? (
            /* Uploaded File Info State */
            <div className="space-y-4">
              <div className="flex items-start gap-3 rounded-lg border border-[#DCE6F0] bg-[#F7F9FC] p-3.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white border border-[#DCE6F0] text-[#0EA5E9] shadow-2xs">
                  <FileText className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p
                    className="text-xs font-semibold text-[#0F2747] truncate"
                    title={filename}
                  >
                    {filename}
                  </p>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5 text-[11px] text-[#58708F]">
                    <span>{formatFileSize(document?.file_size)}</span>
                    <span>•</span>
                    <span>Uploaded {formatDate(document?.created_at || "")}</span>
                  </div>
                </div>
              </div>

              {/* Hidden file input for replace action */}
              <input
                ref={replaceInputRef}
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleReplaceFileChange}
                disabled={!canManage || isUploading}
                className="hidden"
                id={`replace-input-${documentType}`}
              />

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleView}
                  isLoading={isViewing}
                  leftIcon={<ExternalLink className="h-3.5 w-3.5" />}
                  className="flex-1 text-xs"
                >
                  View
                </Button>

                {canManage && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleReplaceClick}
                      disabled={isUploading}
                      isLoading={isUploading}
                      leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
                      className="flex-1 text-xs"
                    >
                      Replace
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setIsRemoveDialogOpen(true)}
                      disabled={isDeleting || isUploading}
                      className="px-2.5"
                      title="Remove document"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </>
                )}
              </div>
            </div>
          ) : (
            /* Empty State: Upload Zone */
            <div className="space-y-2">
              <p className="text-xs text-[#58708F] leading-relaxed mb-3">
                {config.description}
              </p>
              <DocumentUploadZone
                onUpload={(file) => onUpload(documentType, file)}
                isLoading={isUploading}
                disabled={!canManage}
              />
            </div>
          )}
        </div>
      </div>

      {/* Confirmation Dialog for Removal */}
      {document && (
        <RemoveDocumentDialog
          open={isRemoveDialogOpen}
          document={document}
          documentTitle={config.title}
          onOpenChange={setIsRemoveDialogOpen}
          onConfirm={onDelete}
          isLoading={isDeleting}
        />
      )}
    </>
  );
}

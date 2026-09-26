"use client";

import React, { useState, useEffect } from "react";
import { Project, DocumentType } from "@/lib/api/types";
import { documentsApi } from "@/lib/api/endpoints";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { DOCUMENT_TYPE_META } from "./document-type-badge";
import {
  Upload,
  FileText,
  Folder,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadDocumentModalProps {
  open: boolean;
  projects: Project[];
  defaultProjectId?: string;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (projectId: string) => void;
}

export function UploadDocumentModal({
  open,
  projects,
  defaultProjectId = "",
  onOpenChange,
  onSuccess,
}: UploadDocumentModalProps) {
  const [selectedProjectId, setSelectedProjectId] = useState<string>(defaultProjectId);
  const [selectedType, setSelectedType] = useState<DocumentType>("DESIGN");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [statusState, setStatusState] = useState<"IDLE" | "UPLOADING" | "PROCESSING" | "SUCCESS" | "ERROR">("IDLE");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [processingMessage, setProcessingMessage] = useState<string>("Uploading...");

  useEffect(() => {
    if (open) {
      if (defaultProjectId) {
        setSelectedProjectId(defaultProjectId);
      } else if (projects.length > 0 && !selectedProjectId) {
        setSelectedProjectId(projects[0].id);
      }
      setSelectedFile(null);
      setStatusState("IDLE");
      setErrorMessage(null);
    }
  }, [open, defaultProjectId, projects, selectedProjectId]);

  const ACCEPTED_EXTENSIONS = [
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
    ".md",
    ".doc",
    ".docx",
  ];

  const handleFileChange = (file: File | null) => {
    setErrorMessage(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    // File type validation
    const lowerName = file.name.toLowerCase();
    const isAccepted = ACCEPTED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
    if (!isAccepted) {
      setErrorMessage("Unsupported file format. Please upload a PDF, image, or Excel/CSV file.");
      return;
    }
    // File size validation (50 MB)
    const maxBytes = 200 * 1024 * 1024;
    if (file.size > maxBytes) {
      setErrorMessage("File exceeds the maximum size limit of 200 MB.");
      return;
    }

    setSelectedFile(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProjectId) {
      setErrorMessage("Please select a project.");
      return;
    }
    if (!selectedFile) {
      setErrorMessage("Please select a PDF document to upload.");
      return;
    }

    try {
      setStatusState("UPLOADING");
      setProcessingMessage("Uploading...");
      setErrorMessage(null);

      // Simulate status progression text
      const timer = setTimeout(() => {
        setProcessingMessage("Processing document & extracting information...");
      }, 1500);

      await documentsApi.upload(selectedProjectId, selectedType, selectedFile);
      clearTimeout(timer);

      setStatusState("SUCCESS");
      setTimeout(() => {
        if (onSuccess) onSuccess(selectedProjectId);
        onOpenChange(false);
      }, 1200);
    } catch (err: unknown) {
      setStatusState("ERROR");
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to upload document. Please try again."
      );
    }
  };

  const types: DocumentType[] = ["DESIGN", "ORDER", "ACKNOWLEDGEMENT"];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogClose onClose={() => onOpenChange(false)} />
      <DialogHeader>
        <div className="flex items-center gap-2 mb-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#E0F2FE] text-[#0EA5E9]">
            <Upload className="h-4 w-4" />
          </div>
          <DialogTitle className="text-base font-bold text-[#0F2747]">
            Upload Document
          </DialogTitle>
        </div>
        <DialogDescription>
          Upload Design, Purchase Order, or Manufacturer Acknowledgement (PDF, image, or Excel/CSV) for automated cross-checking.
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSubmit} className="space-y-4 py-2">
        {errorMessage && (
          <div className="flex items-center gap-2 rounded-lg border border-[#FECACA] bg-[#FEE2E2] p-3 text-xs text-[#B91C1C]">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {statusState === "UPLOADING" || statusState === "SUCCESS" ? (
          <div className="rounded-xl border border-[#DCE6F0] bg-[#F7F9FC] p-8 text-center space-y-3">
            {statusState === "SUCCESS" ? (
              <>
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#DCFCE7] text-[#16A34A]">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <h4 className="text-sm font-bold text-[#0F2747]">
                  Document Uploaded Successfully
                </h4>
                <p className="text-xs text-[#58708F]">
                  Document added to project and queued for extraction.
                </p>
              </>
            ) : (
              <>
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#E0F2FE] text-[#0EA5E9]">
                  <Loader2 className="h-6 w-6 animate-spin text-[#0EA5E9]" />
                </div>
                <h4 className="text-sm font-bold text-[#0F2747]">
                  {processingMessage}
                </h4>
                <p className="text-xs text-[#58708F]">
                  Please wait while your document is being uploaded securely.
                </p>
              </>
            )}
          </div>
        ) : (
          <>
            {/* Step 1: Project Selection */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-[#0F2747] flex items-center gap-1.5">
                <Folder className="h-3.5 w-3.5 text-[#58708F]" />
                Select Project
              </label>
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-xs font-medium text-[#0F2747] focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
                required
              >
                <option value="" disabled>
                  -- Select a project --
                </option>
                {projects.map((proj) => (
                  <option key={proj.id} value={proj.id}>
                    {proj.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Step 2: Select Document Type */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-[#0F2747]">
                Document Type
              </label>
              <div className="grid grid-cols-3 gap-2">
                {types.map((t) => {
                  const meta = DOCUMENT_TYPE_META[t];
                  const Icon = meta.icon;
                  const isSelected = selectedType === t;
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setSelectedType(t)}
                      className={cn(
                        "flex flex-col items-center justify-center p-3 rounded-lg border text-center transition-all cursor-pointer",
                        isSelected
                          ? "border-[#0EA5E9] bg-[#E0F2FE]/40 text-[#0284C7] ring-1 ring-[#0EA5E9]"
                          : "border-[#DCE6F0] bg-white text-[#58708F] hover:border-[#0EA5E9]/50 hover:bg-[#F7F9FC]"
                      )}
                    >
                      <Icon className={cn("h-4 w-4 mb-1", isSelected ? meta.iconColor : "text-[#58708F]")} />
                      <span className="text-[11px] font-bold leading-tight">
                        {meta.shortLabel}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Step 3: Drag & Drop PDF */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-[#0F2747] flex items-center justify-between">
                <span>Upload Document</span>
                <span className="text-[11px] font-normal text-[#58708F]">
                  Any file type (Max 200 MB)
                </span>
              </label>

              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={cn(
                  "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-all cursor-pointer",
                  isDragOver
                    ? "border-[#0EA5E9] bg-[#E0F2FE]/30"
                    : selectedFile
                    ? "border-[#16A34A] bg-[#DCFCE7]/20"
                    : "border-[#DCE6F0] bg-[#F7F9FC] hover:border-[#0EA5E9]/50"
                )}
              >
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.gif,.bmp,.webp,.tif,.tiff,.xls,.xlsx,.csv,.txt,.md,.doc,.docx"
                  onChange={(e) =>
                    handleFileChange(e.target.files ? e.target.files[0] : null)
                  }
                  className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                />

                {selectedFile ? (
                  <div className="flex items-center gap-3 w-full justify-between px-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#DCFCE7] text-[#16A34A]">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div className="text-left min-w-0">
                        <p className="text-xs font-bold text-[#0F2747] truncate">
                          {selectedFile.name}
                        </p>
                        <p className="text-[11px] text-[#58708F]">
                          {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFile(null);
                      }}
                      className="text-[#58708F] hover:text-[#DC2626] p-1 rounded-md"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white border border-[#DCE6F0] text-[#0EA5E9] mb-2 shadow-2xs">
                      <Upload className="h-5 w-5" />
                    </div>
                    <p className="text-xs font-semibold text-[#0F2747]">
                      Click to browse or drag & drop a file
                    </p>
                    <p className="text-[11px] text-[#58708F] mt-0.5">
                      Supports PDF, images (JPG/PNG/etc.), and Excel/CSV for Design drawings, Purchase Orders, and Factory Acknowledgements
                    </p>
                  </>
                )}
              </div>
            </div>
          </>
        )}

        <DialogFooter className="pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={statusState === "UPLOADING"}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="default"
            disabled={!selectedFile || !selectedProjectId || statusState === "UPLOADING"}
            isLoading={statusState === "UPLOADING"}
            leftIcon={<Upload className="h-4 w-4" />}
          >
            Upload & Process
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}

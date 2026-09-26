"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, Loader2, AlertCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DocumentUploadZoneProps {
  onUpload: (file: File) => Promise<void>;
  isLoading?: boolean;
  disabled?: boolean;
  className?: string;
  accept?: string;
  maxSizeMB?: number;
}

export function DocumentUploadZone({
  onUpload,
  isLoading = false,
  disabled = false,
  className,
  accept = ".pdf,.jpg,.jpeg,.png,.gif,.bmp,.webp,.tif,.tiff,.xls,.xlsx,.csv,.txt,.md,.doc,.docx",
  maxSizeMB = 200,
}: DocumentUploadZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const validateAndProcessFile = async (file: File) => {
    setError(null);

    // Validate type
    const lowerName = file.name.toLowerCase();
    const isAccepted = ACCEPTED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
    if (!isAccepted) {
      setError("Unsupported file format. Please upload a PDF, image, or Excel/CSV file.");
      return;
    }

    // Validate size
    const maxBytes = maxSizeMB * 1024 * 1024;
    if (file.size > maxBytes) {
      setError(`File size exceeds ${maxSizeMB} MB limit.`);
      return;
    }

    setSelectedFile(file);

    try {
      await onUpload(file);
      setSelectedFile(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled && !isLoading) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (disabled || isLoading) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      validateAndProcessFile(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      validateAndProcessFile(file);
      // Reset input value so same file can be selected again if needed
      e.target.value = "";
    }
  };

  const triggerFileInput = () => {
    if (disabled || isLoading) return;
    fileInputRef.current?.click();
  };

  // If upload is currently in progress
  if (isLoading && selectedFile) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-[#0EA5E9]/40 bg-[#E0F2FE]/20 p-6 text-center space-y-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#E0F2FE] text-[#0EA5E9]">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
        <div className="space-y-1">
          <p className="text-xs font-bold text-[#0F2747] truncate max-w-[240px]">
            {selectedFile.name}
          </p>
          <p className="text-[11px] text-[#58708F]">
            Uploading document ({(selectedFile.size / (1024 * 1024)).toFixed(2)} MB)...
          </p>
        </div>
        <div className="w-full max-w-[200px] h-1.5 rounded-full bg-[#DCE6F0] overflow-hidden">
          <div className="h-full bg-[#0EA5E9] rounded-full animate-pulse w-3/4" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        onChange={handleFileInputChange}
        disabled={disabled || isLoading}
        className="hidden"
        id="file-upload-input"
      />

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={triggerFileInput}
        className={cn(
          "flex flex-col items-center justify-center rounded-xl border border-dashed p-6 text-center transition-all cursor-pointer select-none",
          isDragOver
            ? "border-[#0EA5E9] bg-[#E0F2FE]/30 scale-[0.99]"
            : "border-[#DCE6F0] bg-white hover:bg-[#F7F9FC] hover:border-[#0EA5E9]/50",
          disabled && "opacity-60 cursor-not-allowed hover:bg-white hover:border-[#DCE6F0]",
          className
        )}
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#E0F2FE] text-[#0EA5E9] mb-3 shadow-2xs">
          <UploadCloud className="h-5 w-5" />
        </div>

        <p className="text-xs font-semibold text-[#0F2747]">
          Drop your file here
        </p>
        <p className="text-[11px] text-[#58708F] mt-0.5">
          or <span className="font-semibold text-[#0284C7] hover:underline">browse from your computer</span>
        </p>

        <span className="mt-3 inline-block rounded-full bg-[#F7F9FC] px-2.5 py-0.5 text-[10px] font-medium text-[#58708F] border border-[#DCE6F0]">
          Any file type up to {maxSizeMB} MB
        </span>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-[#FECACA] bg-[#FEE2E2] p-2.5 text-xs text-[#B91C1C]">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Upload failed: </span>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setError(null);
            }}
            className="text-[#B91C1C] hover:opacity-80 p-0.5"
            title="Dismiss"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

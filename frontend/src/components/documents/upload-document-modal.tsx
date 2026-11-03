"use client";

import React, { useState, useEffect } from "react";
import { Project, DocumentType } from "@/lib/api/types";
import { documentsApi } from "@/lib/api/endpoints";
import { useCreateProject } from "@/lib/hooks/use-projects";
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

const DOC_TYPES: DocumentType[] = ["DESIGN", "ORDER", "ACKNOWLEDGEMENT"];
const NEW_PROJECT_VALUE = "__new__";

const ACCEPTED_EXTENSIONS = [
  ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff",
  ".xls", ".xlsx", ".csv", ".txt", ".md", ".doc", ".docx",
];
const MAX_BYTES = 200 * 1024 * 1024;

type SlotStatus = "idle" | "uploading" | "success" | "error";
interface SlotState {
  file: File | null;
  status: SlotStatus;
  error: string | null;
}
const emptySlots = (): Record<DocumentType, SlotState> => ({
  DESIGN: { file: null, status: "idle", error: null },
  ORDER: { file: null, status: "idle", error: null },
  ACKNOWLEDGEMENT: { file: null, status: "idle", error: null },
});

// One dropzone for one document type — all three render side by side so a
// project's Design/Order/Acknowledgement can be uploaded in a single pass
// instead of reopening this modal three times.
function DocumentSlot({
  type,
  slot,
  dragOver,
  onFile,
  onClear,
  onDragOver,
  onDragLeave,
  onDrop,
}: {
  type: DocumentType;
  slot: SlotState;
  dragOver: boolean;
  onFile: (file: File | null) => void;
  onClear: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
}) {
  const meta = DOCUMENT_TYPE_META[type];
  const Icon = meta.icon;
  const locked = slot.status === "uploading" || slot.status === "success";

  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-1.5 text-xs font-bold text-[#0F2747]">
        <Icon className={cn("h-3.5 w-3.5", meta.iconColor)} />
        {meta.shortLabel}
      </label>
      <div
        onDragOver={locked ? undefined : onDragOver}
        onDragLeave={locked ? undefined : onDragLeave}
        onDrop={locked ? undefined : onDrop}
        className={cn(
          "relative flex min-h-28 flex-col items-center justify-center rounded-xl border-2 border-dashed p-3 text-center transition-all",
          slot.status === "success"
            ? "border-[#16A34A] bg-[#DCFCE7]/30"
            : slot.status === "error"
            ? "border-[#DC2626] bg-[#FEE2E2]/30"
            : dragOver
            ? "border-[#0EA5E9] bg-[#E0F2FE]/30"
            : slot.file
            ? "border-[#0EA5E9] bg-[#E0F2FE]/20"
            : "border-[#DCE6F0] bg-[#F7F9FC] hover:border-[#0EA5E9]/50"
        )}
      >
        {!locked && (
          <input
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            onChange={(e) => onFile(e.target.files ? e.target.files[0] : null)}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
          />
        )}

        {slot.status === "uploading" ? (
          <Loader2 className="h-5 w-5 animate-spin text-[#0EA5E9]" />
        ) : slot.status === "success" ? (
          <>
            <CheckCircle2 className="h-5 w-5 text-[#16A34A]" />
            <p className="mt-1 text-[11px] font-semibold text-[#15803D]">Uploaded</p>
          </>
        ) : slot.file ? (
          <div className="flex w-full min-w-0 items-center justify-between gap-1.5">
            <div className="flex min-w-0 items-center gap-1.5">
              <FileText className="h-4 w-4 shrink-0 text-[#0284C7]" />
              <span className="truncate text-[11px] font-semibold text-[#0F2747]">
                {slot.file.name}
              </span>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onClear();
              }}
              className="shrink-0 rounded-md p-0.5 text-[#58708F] hover:text-[#DC2626]"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <>
            <Upload className="h-4 w-4 text-[#58708F]" />
            <p className="mt-1 text-[11px] font-semibold text-[#58708F]">
              Click or drag file
            </p>
          </>
        )}
      </div>
      {slot.status === "error" && slot.error && (
        <p className="text-[11px] text-[#DC2626]">{slot.error}</p>
      )}
    </div>
  );
}

export function UploadDocumentModal({
  open,
  projects,
  defaultProjectId = "",
  onOpenChange,
  onSuccess,
}: UploadDocumentModalProps) {
  const createProject = useCreateProject();
  const [selectedProjectId, setSelectedProjectId] = useState<string>(defaultProjectId);
  const [newProjectName, setNewProjectName] = useState("");
  const [slots, setSlots] = useState<Record<DocumentType, SlotState>>(emptySlots());
  const [dragOverType, setDragOverType] = useState<DocumentType | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      if (defaultProjectId) {
        setSelectedProjectId(defaultProjectId);
      } else if (projects.length === 0) {
        setSelectedProjectId(NEW_PROJECT_VALUE);
      } else if (!selectedProjectId) {
        setSelectedProjectId(projects[0].id);
      }
      setNewProjectName("");
      setSlots(emptySlots());
      setFormError(null);
      setIsSubmitting(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, defaultProjectId, projects]);

  const validateFile = (file: File): string | null => {
    const lowerName = file.name.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.some((ext) => lowerName.endsWith(ext))) {
      return "Unsupported file format.";
    }
    if (file.size > MAX_BYTES) {
      return "File exceeds the 200 MB limit.";
    }
    return null;
  };

  const setSlot = (type: DocumentType, patch: Partial<SlotState>) =>
    setSlots((prev) => ({ ...prev, [type]: { ...prev[type], ...patch } }));

  const handleFile = (type: DocumentType, file: File | null) => {
    setFormError(null);
    if (!file) {
      setSlot(type, { file: null, status: "idle", error: null });
      return;
    }
    const error = validateFile(file);
    setSlot(type, error ? { file: null, status: "idle", error } : { file, status: "idle", error: null });
  };

  const pendingTypes = DOC_TYPES.filter((t) => slots[t].file && slots[t].status !== "success");
  const anyUploaded = DOC_TYPES.some((t) => slots[t].status === "success");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProjectId) {
      setFormError("Please select a project.");
      return;
    }
    if (selectedProjectId === NEW_PROJECT_VALUE && !newProjectName.trim()) {
      setFormError("Please enter a project name.");
      return;
    }
    if (pendingTypes.length === 0) {
      setFormError("Add at least one file to upload.");
      return;
    }

    setFormError(null);
    setIsSubmitting(true);

    let projectId = selectedProjectId;
    if (selectedProjectId === NEW_PROJECT_VALUE) {
      try {
        const created = await createProject.mutateAsync({ name: newProjectName.trim() });
        projectId = created.id;
      } catch {
        setFormError("Failed to create project. Please try again.");
        setIsSubmitting(false);
        return;
      }
    }

    pendingTypes.forEach((t) => setSlot(t, { status: "uploading", error: null }));

    const results = await Promise.allSettled(
      pendingTypes.map((t) => documentsApi.upload(projectId, t, slots[t].file as File))
    );

    results.forEach((res, i) => {
      const t = pendingTypes[i];
      if (res.status === "fulfilled") {
        setSlot(t, { status: "success", error: null });
      } else {
        setSlot(t, {
          status: "error",
          error: res.reason instanceof Error ? res.reason.message : "Upload failed.",
        });
      }
    });

    setIsSubmitting(false);

    if (results.every((r) => r.status === "fulfilled")) {
      setTimeout(() => {
        if (onSuccess) onSuccess(projectId);
        onOpenChange(false);
      }, 900);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogClose onClose={() => onOpenChange(false)} />
      <DialogHeader>
        <div className="mb-1 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#E0F2FE] text-[#0EA5E9]">
            <Upload className="h-4 w-4" />
          </div>
          <DialogTitle className="text-base font-bold text-[#0F2747]">
            Upload Documents
          </DialogTitle>
        </div>
        <DialogDescription>
          Add whichever documents you have — Design, Purchase Order, and/or Manufacturer
          Acknowledgement — in one go. Processing starts automatically once all three are in.
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSubmit} className="space-y-4 py-2">
        {formError && (
          <div className="flex items-center gap-2 rounded-lg border border-[#FECACA] bg-[#FEE2E2] p-3 text-xs text-[#B91C1C]">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{formError}</span>
          </div>
        )}

        <div className="space-y-1.5">
          <label className="flex items-center gap-1.5 text-xs font-bold text-[#0F2747]">
            <Folder className="h-3.5 w-3.5 text-[#58708F]" />
            Project
          </label>
          <select
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            disabled={isSubmitting}
            className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-xs font-medium text-[#0F2747] focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
            required
          >
            <option value="" disabled>
              -- Select a project --
            </option>
            <option value={NEW_PROJECT_VALUE}>➕ Create New Project</option>
            {projects.map((proj) => (
              <option key={proj.id} value={proj.id}>
                {proj.name}
              </option>
            ))}
          </select>
          {selectedProjectId === NEW_PROJECT_VALUE && (
            <input
              type="text"
              placeholder="Project name (e.g. Hartland Kitchen)"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              disabled={isSubmitting}
              className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-xs font-medium text-[#0F2747] placeholder:text-[#A0B0C4] focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
              autoFocus
            />
          )}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {DOC_TYPES.map((t) => (
            <DocumentSlot
              key={t}
              type={t}
              slot={slots[t]}
              dragOver={dragOverType === t}
              onFile={(file) => handleFile(t, file)}
              onClear={() => handleFile(t, null)}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOverType(t);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setDragOverType(null);
              }}
              onDrop={(e) => {
                e.preventDefault();
                setDragOverType(null);
                if (e.dataTransfer.files?.[0]) handleFile(t, e.dataTransfer.files[0]);
              }}
            />
          ))}
        </div>
        <p className="text-[11px] text-[#58708F]">
          Any file type accepted (PDF, image, Excel/CSV), max 200 MB each.
        </p>

        <DialogFooter className="pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            {anyUploaded ? "Done" : "Cancel"}
          </Button>
          <Button
            type="submit"
            variant="default"
            disabled={pendingTypes.length === 0 || isSubmitting}
            isLoading={isSubmitting}
            leftIcon={<Upload className="h-4 w-4" />}
          >
            {pendingTypes.length > 1 ? `Upload ${pendingTypes.length} Documents` : "Upload & Process"}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}

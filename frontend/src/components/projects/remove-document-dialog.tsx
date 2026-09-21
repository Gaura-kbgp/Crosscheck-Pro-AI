"use client";

import React, { useState } from "react";
import { Document } from "@/lib/api/types";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Trash2 } from "lucide-react";

interface RemoveDocumentDialogProps {
  open: boolean;
  document: Document | null;
  documentTitle: string;
  onOpenChange: (open: boolean) => void;
  onConfirm: (documentId: string) => Promise<void>;
  isLoading?: boolean;
}

export function RemoveDocumentDialog({
  open,
  document,
  documentTitle,
  onOpenChange,
  onConfirm,
  isLoading = false,
}: RemoveDocumentDialogProps) {
  const [error, setError] = useState<string | null>(null);

  if (!document) return null;

  const handleRemove = async () => {
    setError(null);
    try {
      await onConfirm(document.id);
      onOpenChange(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to remove document.");
    }
  };

  const filename = document.original_filename || document.filename || "Uploaded PDF";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogClose onClose={() => onOpenChange(false)} />
      <DialogHeader>
        <div className="flex items-center gap-2.5 mb-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#FEE2E2] text-[#DC2626]">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <DialogTitle>Remove {documentTitle}?</DialogTitle>
        </div>
        <DialogDescription>
          Are you sure you want to remove <strong className="text-[#0F2747] font-semibold">{filename}</strong>? 
          Any pending or extracted candidate data associated with this document will be discarded.
        </DialogDescription>
      </DialogHeader>

      {error && (
        <div className="rounded-lg border border-[#FECACA] bg-[#FEE2E2] p-3 text-xs text-[#B91C1C] mb-4">
          {error}
        </div>
      )}

      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          onClick={() => onOpenChange(false)}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button
          type="button"
          variant="destructive"
          onClick={handleRemove}
          isLoading={isLoading}
          leftIcon={<Trash2 className="h-4 w-4" />}
        >
          Remove Document
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

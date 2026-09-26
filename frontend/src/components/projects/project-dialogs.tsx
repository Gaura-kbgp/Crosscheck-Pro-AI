"use client";

import React, { useState } from "react";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Project, ProjectCreateInput, ProjectUpdateInput } from "@/lib/api/types";
import { Building2, FolderKanban, AlertTriangle, Trash2 } from "lucide-react";
import { useManufacturers } from "@/lib/hooks/use-manufacturers";

function ManufacturerSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { data: manufacturers } = useManufacturers();
  return (
    <div>
      <label className="block text-xs font-semibold text-[#0F2747] mb-1">Manufacturer</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-sm text-[#0F2747] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors"
      >
        <option value="">Not specified</option>
        {(manufacturers || []).map((m) => (
          <option key={m.id} value={m.id}>{m.name}{m.is_global ? " (Global)" : ""}</option>
        ))}
      </select>
    </div>
  );
}

interface CreateProjectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: ProjectCreateInput) => Promise<void>;
  isLoading: boolean;
}

function CreateProjectForm({
  onClose,
  onSubmit,
  isLoading,
}: {
  onClose: () => void;
  onSubmit: (data: ProjectCreateInput) => Promise<void>;
  isLoading: boolean;
}) {
  const [name, setName] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [dealerName, setDealerName] = useState("");
  const [manufacturerId, setManufacturerId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Project name is required.");
      return;
    }
    setError(null);
    try {
      await onSubmit({
        name: name.trim(),
        customer_name: customerName.trim() || undefined,
        dealer_name: dealerName.trim() || undefined,
        manufacturer_id: manufacturerId || null,
      });
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
    }
  };

  return (
    <>
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <div className="flex items-center gap-2 mb-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#E0F2FE] text-[#0284C7]">
            <FolderKanban className="h-4 w-4" />
          </div>
          <DialogTitle>Create New Project</DialogTitle>
        </div>
        <DialogDescription>
          Start a new construction document verification workspace.
        </DialogDescription>
      </DialogHeader>

      {error && (
        <Alert variant="destructive" className="mb-4">
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="projectName"
            className="block text-xs font-semibold text-[#0F2747] mb-1"
          >
            Project Name <span className="text-[#DC2626]">*</span>
          </label>
          <input
            id="projectName"
            type="text"
            required
            placeholder="e.g. Apex Commercial Tower - Phase 1"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-sm text-[#0F2747] placeholder:text-[#58708F] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="customerName"
              className="block text-xs font-semibold text-[#0F2747] mb-1"
            >
              Customer Name
            </label>
            <input
              id="customerName"
              type="text"
              placeholder="e.g. Apex Developments LLC"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-sm text-[#0F2747] placeholder:text-[#58708F] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors"
            />
          </div>

          <div>
            <label
              htmlFor="dealerName"
              className="block text-xs font-semibold text-[#0F2747] mb-1"
            >
              Dealer / Contractor
            </label>
            <input
              id="dealerName"
              type="text"
              placeholder="e.g. Skyline Interiors"
              value={dealerName}
              onChange={(e) => setDealerName(e.target.value)}
              className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-sm text-[#0F2747] placeholder:text-[#58708F] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors"
            />
          </div>
        </div>

        <ManufacturerSelect value={manufacturerId} onChange={setManufacturerId} />

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            isLoading={isLoading}
          >
            Create Project
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

export function CreateProjectDialog({
  open,
  onOpenChange,
  onSubmit,
  isLoading,
}: CreateProjectDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <CreateProjectForm
          key="create-form"
          onClose={() => onOpenChange(false)}
          onSubmit={onSubmit}
          isLoading={isLoading}
        />
      )}
    </Dialog>
  );
}

interface EditProjectDialogProps {
  open: boolean;
  project: Project | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (id: string, data: ProjectUpdateInput) => Promise<void>;
  isLoading: boolean;
}

function EditProjectForm({
  project,
  onClose,
  onSubmit,
  isLoading,
}: {
  project: Project;
  onClose: () => void;
  onSubmit: (id: string, data: ProjectUpdateInput) => Promise<void>;
  isLoading: boolean;
}) {
  const [name, setName] = useState(project.name || "");
  const [customerName, setCustomerName] = useState(project.customer_name || "");
  const [dealerName, setDealerName] = useState(project.dealer_name || "");
  const [manufacturerId, setManufacturerId] = useState(project.manufacturer_id || "");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Project name is required.");
      return;
    }
    setError(null);
    try {
      await onSubmit(project.id, {
        name: name.trim(),
        customer_name: customerName.trim() || undefined,
        dealer_name: dealerName.trim() || undefined,
        manufacturer_id: manufacturerId || null,
      });
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update project.");
    }
  };

  return (
    <>
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <div className="flex items-center gap-2 mb-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#E0F2FE] text-[#0284C7]">
            <Building2 className="h-4 w-4" />
          </div>
          <DialogTitle>Edit Project</DialogTitle>
        </div>
        <DialogDescription>
          Update project details and customer information.
        </DialogDescription>
      </DialogHeader>

      {error && (
        <Alert variant="destructive" className="mb-4">
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="editProjectName"
            className="block text-xs font-semibold text-[#0F2747] mb-1"
          >
            Project Name <span className="text-[#DC2626]">*</span>
          </label>
          <input
            id="editProjectName"
            type="text"
            required
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-sm text-[#0F2747] placeholder:text-[#58708F] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="editCustomerName"
              className="block text-xs font-semibold text-[#0F2747] mb-1"
            >
              Customer Name
            </label>
            <input
              id="editCustomerName"
              type="text"
              placeholder="Customer name"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-sm text-[#0F2747] placeholder:text-[#58708F] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors"
            />
          </div>

          <div>
            <label
              htmlFor="editDealerName"
              className="block text-xs font-semibold text-[#0F2747] mb-1"
            >
              Dealer / Contractor
            </label>
            <input
              id="editDealerName"
              type="text"
              placeholder="Dealer name"
              value={dealerName}
              onChange={(e) => setDealerName(e.target.value)}
              className="w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-2 text-sm text-[#0F2747] placeholder:text-[#58708F] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors"
            />
          </div>
        </div>

        <ManufacturerSelect value={manufacturerId} onChange={setManufacturerId} />

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            isLoading={isLoading}
          >
            Save Changes
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

export function EditProjectDialog({
  open,
  project,
  onOpenChange,
  onSubmit,
  isLoading,
}: EditProjectDialogProps) {
  if (!project) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <EditProjectForm
          key={project.id}
          project={project}
          onClose={() => onOpenChange(false)}
          onSubmit={onSubmit}
          isLoading={isLoading}
        />
      )}
    </Dialog>
  );
}

interface DeleteProjectDialogProps {
  open: boolean;
  project: Project | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: (id: string) => Promise<void>;
  isLoading: boolean;
}

function DeleteProjectForm({
  project,
  onClose,
  onConfirm,
  isLoading,
}: {
  project: Project;
  onClose: () => void;
  onConfirm: (id: string) => Promise<void>;
  isLoading: boolean;
}) {
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    try {
      await onConfirm(project.id);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete project.");
    }
  };

  return (
    <>
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <div className="flex items-center gap-2 mb-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#FEE2E2] text-[#DC2626]">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <DialogTitle>Delete Project?</DialogTitle>
        </div>
        <DialogDescription>
          This action cannot be undone. All documents, extracted items, cross-check discrepancies, and reports associated with <strong className="text-[#0F2747] font-semibold">{project.name}</strong> will be permanently deleted.
        </DialogDescription>
      </DialogHeader>

      {error && (
        <Alert variant="destructive" className="mb-4">
          {error}
        </Alert>
      )}

      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          onClick={onClose}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button
          type="button"
          variant="destructive"
          className="gap-1.5"
          onClick={handleDelete}
          isLoading={isLoading}
        >
          <Trash2 className="h-4 w-4" />
          Delete Project
        </Button>
      </DialogFooter>
    </>
  );
}

export function DeleteProjectDialog({
  open,
  project,
  onOpenChange,
  onConfirm,
  isLoading,
}: DeleteProjectDialogProps) {
  if (!project) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <DeleteProjectForm
          key={project.id}
          project={project}
          onClose={() => onOpenChange(false)}
          onConfirm={onConfirm}
          isLoading={isLoading}
        />
      )}
    </Dialog>
  );
}

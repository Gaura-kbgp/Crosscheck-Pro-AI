import React from "react";
import { Dialog, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useFinalizeProject } from "@/lib/hooks/use-reviews";
import { toast } from "sonner";
import { ShieldCheck, AlertTriangle } from "lucide-react";
import { useRouter } from "next/navigation";

interface FinalizeProjectDialogProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  /** Open (unresolved) CRITICAL discrepancies — the backend blocks finalize while this is > 0. */
  openCriticalCount?: number;
}

export function FinalizeProjectDialog({ projectId, isOpen, onClose, openCriticalCount = 0 }: FinalizeProjectDialogProps) {
  const finalizeMutation = useFinalizeProject(projectId);
  const router = useRouter();
  const isBlocked = openCriticalCount > 0;

  const handleFinalize = async () => {
    try {
      await finalizeMutation.mutateAsync();
      toast.success("Project finalized successfully!");
      onClose();
      // Redirect to project detail view since review is now read-only
      router.push(`/projects/${projectId}`);
    } catch (err: any) {
      toast.error(err.message || "Failed to finalize project. Please resolve all blocking discrepancies first.");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <div className="flex flex-col gap-4">
        <DialogHeader>
          <div className={`mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-4 ${isBlocked ? "bg-rose-100" : "bg-emerald-100"}`}>
            {isBlocked ? (
              <AlertTriangle className="h-6 w-6 text-rose-600" />
            ) : (
              <ShieldCheck className="h-6 w-6 text-emerald-600" />
            )}
          </div>
          <DialogTitle className="text-center">Finalize Project</DialogTitle>
          <DialogDescription className="text-center text-slate-600">
            {isBlocked
              ? "This project can't be finalized yet."
              : "Are you sure you want to finalize this project?"}
          </DialogDescription>
        </DialogHeader>

        {isBlocked ? (
          <div className="bg-rose-50 border border-rose-200 rounded-lg p-4 text-sm text-rose-800">
            <p className="font-semibold">
              {openCriticalCount} critical discrepanc{openCriticalCount === 1 ? "y is" : "ies are"} still open.
            </p>
            <p className="mt-1">
              Resolve (accept, reject, or override) every critical finding in Human Review before finalizing —
              a finalized project can't be edited afterward.
            </p>
          </div>
        ) : (
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm text-slate-700 mt-2 space-y-2">
            <p className="font-semibold text-slate-900">What happens next:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>The project will be locked from further edits.</li>
              <li>Review decisions will become part of the final audit trail.</li>
              <li>Reports can be generated.</li>
            </ul>
          </div>
        )}

        <DialogFooter className="mt-6 sm:justify-center">
          <Button type="button" variant="outline" onClick={onClose} className="w-full sm:w-auto">
            {isBlocked ? "Close" : "Cancel"}
          </Button>
          {!isBlocked && (
            <Button
              type="button"
              onClick={handleFinalize}
              className="w-full sm:w-auto bg-[#16A34A] hover:bg-[#15803D] text-white"
              isLoading={finalizeMutation.isPending}
            >
              Confirm Finalization
            </Button>
          )}
        </DialogFooter>
      </div>
    </Dialog>
  );
}

import React from "react";
import { Dialog, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useFinalizeProject } from "@/lib/hooks/use-reviews";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";

interface FinalizeProjectDialogProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function FinalizeProjectDialog({ projectId, isOpen, onClose }: FinalizeProjectDialogProps) {
  const finalizeMutation = useFinalizeProject(projectId);
  const router = useRouter();

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
          <div className="mx-auto w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mb-4">
            <ShieldCheck className="h-6 w-6 text-emerald-600" />
          </div>
          <DialogTitle className="text-center">Finalize Project</DialogTitle>
          <DialogDescription className="text-center text-slate-600">
            Are you sure you want to finalize this project?
          </DialogDescription>
        </DialogHeader>

        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm text-slate-700 mt-2 space-y-2">
          <p className="font-semibold text-slate-900">What happens next:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>The project will be locked from further edits.</li>
            <li>Review decisions will become part of the final audit trail.</li>
            <li>Reports can be generated.</li>
          </ul>
        </div>

        <DialogFooter className="mt-6 sm:justify-center">
          <Button type="button" variant="outline" onClick={onClose} className="w-full sm:w-auto">
            Cancel
          </Button>
          <Button 
            type="button" 
            onClick={handleFinalize}
            className="w-full sm:w-auto bg-[#16A34A] hover:bg-[#15803D] text-white"
            isLoading={finalizeMutation.isPending}
          >
            Confirm Finalization
          </Button>
        </DialogFooter>
      </div>
    </Dialog>
  );
}

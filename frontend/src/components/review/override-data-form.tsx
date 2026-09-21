import React, { useState } from "react";
import { Dialog, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Discrepancy, MatchGroup } from "@/lib/api/types";
import { useReviewAction } from "@/lib/hooks/use-reviews";
import { toast } from "sonner";
import { AlertCircle } from "lucide-react";

interface OverrideDataFormProps {
  isOpen: boolean;
  onClose: () => void;
  discrepancy: Discrepancy;
  group: MatchGroup;
  projectId: string;
}

export function OverrideDataForm({ isOpen, onClose, discrepancy, group, projectId }: OverrideDataFormProps) {
  const [newValue, setNewValue] = useState("");
  const [reason, setReason] = useState("");
  
  const actionMutation = useReviewAction(projectId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      toast.error("A reason is required to override data.");
      return;
    }

    try {
      await actionMutation.mutateAsync({
        discrepancyId: discrepancy.id,
        data: {
          action: "OVERRIDE_DATA",
          reason: reason.trim(),
          match_group_id: group.id,
          canonical_item_id: group.canonical_item_id || group.id, // Fallback to group id if for some reason canonical_item_id is null
          field_name: discrepancy.field_name,
          new_value: newValue,
        }
      });
      toast.success(`Data overridden successfully for ${discrepancy.field_name}`);
      onClose();
    } catch (err: any) {
      toast.error(err.message || "Failed to override data");
    }
  };

  // Pre-fill when opening if empty
  React.useEffect(() => {
    if (isOpen) {
      setNewValue("");
      setReason("");
    }
  }, [isOpen]);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <div className="flex flex-col gap-4">
        <DialogHeader>
          <DialogTitle>Override Data</DialogTitle>
          <DialogDescription>
            Manually set the final accepted value for this field. This will recalculate the final state of the match group.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <div className="bg-sky-50 p-3 rounded-lg border border-sky-100 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-sky-600 shrink-0 mt-0.5" />
            <div className="text-sm text-sky-900">
              <span className="font-bold">Field:</span> {discrepancy.field_name}
              <br />
              <span className="font-bold">SKU:</span> {group.canonical_sku}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-bold text-[#0F2747]">New Final Value</label>
            <input
              type="text"
              required
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              className="w-full border border-[#DCE6F0] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]"
              placeholder={`Enter correct value for ${discrepancy.field_name}`}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-bold text-[#0F2747]">Reason for Override <span className="text-rose-500">*</span></label>
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full border border-[#DCE6F0] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0EA5E9] min-h-[80px] resize-y"
              placeholder="E.g., Manufacturer confirmed revised quantity."
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button 
              type="submit" 
              className="bg-[#0B8FD3] hover:bg-[#0EA5E9] text-white"
              isLoading={actionMutation.isPending}
            >
              Submit Override
            </Button>
          </DialogFooter>
        </form>
      </div>
    </Dialog>
  );
}

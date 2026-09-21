"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { useCrossCheck } from "@/lib/hooks/use-crosscheck";
import { useGenerateReport, useDownloadCsv } from "@/lib/hooks/use-reports";
import { FileDown, FileText, Loader2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

import { useAuthStore } from "@/lib/store/auth-store";

interface ReportSummaryProps {
  projectId: string;
}

export function ReportSummary({ projectId }: ReportSummaryProps) {
  const { profile } = useAuthStore();
  const userRole = profile?.role || "VIEWER";
  const canManage = userRole === "ADMIN" || userRole === "REVIEWER";

  const { data: crosscheck, isLoading: isCrosscheckLoading } = useCrossCheck(projectId);
  const generateMutation = useGenerateReport(projectId);
  const handleDownloadCsv = useDownloadCsv(projectId);
  
  const [isExportingCsv, setIsExportingCsv] = useState(false);

  const handleGeneratePdf = async () => {
    try {
      await generateMutation.mutateAsync({ format: "PDF" });
      toast.success("PDF Report generation started");
    } catch (err: unknown) {
      toast.error(
        err instanceof Error
          ? err.message
          : "Failed to start PDF generation"
      );
    }
  };

  const onExportCsv = async () => {
    setIsExportingCsv(true);
    try {
      await handleDownloadCsv();
      toast.success("CSV Export downloaded successfully");
    } catch (err: unknown) {
      toast.error(
        err instanceof Error
          ? err.message
          : "Failed to download CSV"
      );
    } finally {
      setIsExportingCsv(false);
    }
  };

  if (isCrosscheckLoading) {
    return <Skeleton className="h-48 w-full rounded-xl" />;
  }

  if (!crosscheck) return null;

  const { summary } = crosscheck;

  return (
    <div className="bg-white rounded-xl border border-[#DCE6F0] shadow-2xs p-5 sm:p-6 mb-6">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
        {/* Left Side: Summary Metrics */}
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-bold text-[#0F2747]">Cross-Check Summary</h2>
            <p className="text-sm text-[#58708F] mt-1">Finalized metrics based on the latest cross-check data.</p>
          </div>
          
          <div className="flex gap-8">
            <div className="flex flex-col gap-1">
              <span className="text-[11px] font-semibold text-[#58708F] uppercase tracking-wider">Total Items</span>
              <span className="text-2xl font-bold text-[#0F2747]">{summary.total_groups}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[11px] font-semibold text-[#58708F] uppercase tracking-wider">Matched</span>
              <span className="text-2xl font-bold text-[#16A34A]">{summary.matched}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[11px] font-semibold text-[#58708F] uppercase tracking-wider">Discrepancies</span>
              <span className="text-2xl font-bold text-[#DC2626]">
                {summary.changed + summary.missing + summary.extra + summary.uncertain}
              </span>
            </div>
          </div>
        </div>

        {/* Right Side: Actions */}
        <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto shrink-0">
          <Button
            variant="outline"
            onClick={onExportCsv}
            disabled={isExportingCsv}
            className="w-full sm:w-auto whitespace-nowrap bg-white border-[#DCE6F0] hover:bg-[#F7F9FC]"
          >
            {isExportingCsv ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileDown className="mr-2 h-4 w-4" />}
            Export CSV
          </Button>
          {canManage && (
            <Button
              variant="default"
              onClick={handleGeneratePdf}
              disabled={generateMutation.isPending}
              className="w-full sm:w-auto whitespace-nowrap bg-[#0EA5E9] hover:bg-[#0284C7] text-white"
            >
              {generateMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileText className="mr-2 h-4 w-4" />}
              Generate PDF Report
            </Button>
          )}
        </div>
      </div>
      
      {/* Optional Attention Banner */}
      {summary.open_reviews > 0 && (
        <div className="mt-6 flex items-start gap-2.5 rounded-lg border border-[#FDE68A] bg-[#FEF3C7] p-3 text-xs text-[#D97706]">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Notice: </span>
            <span>There are {summary.open_reviews} open reviews. Reports generated now will include unresolved discrepancies.</span>
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import React, { useState } from "react";
import { useProjectReports, useReportStatus } from "@/lib/hooks/use-reports";
import { Report, ReportStatus } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Download, Loader2, AlertCircle, FileText, CheckCircle2, Clock } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// Component to handle polling and downloading for a single report row
function ReportRow({ report }: { report: Report }) {
  // If report is not completed, we poll its status
  const isPolling = report.status === "QUEUED" || report.status === "GENERATING";
  const { data: polledReport } = useReportStatus(report.id, isPolling);
  
  // Use the latest data, fallback to initial report data
  const currentReport = polledReport || report;
  
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = () => {
    if (!currentReport.download_url) {
      toast.error("Download URL not available");
      return;
    }
    
    // Trigger download
    setIsDownloading(true);
    const a = document.createElement("a");
    a.href = currentReport.download_url;
    // We assume backend issues pre-signed URL or direct file download endpoint
    a.target = "_blank";
    a.download = `report_${currentReport.id}.${currentReport.format.toLowerCase()}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setIsDownloading(false);
  };

  const getStatusBadge = (status: ReportStatus) => {
    switch (status) {
      case "COMPLETED":
        return <span className="inline-flex items-center rounded-full bg-[#DCFCE7] px-2 py-0.5 text-xs font-medium text-[#16A34A]">Completed</span>;
      case "FAILED":
        return <span className="inline-flex items-center rounded-full bg-[#FEE2E2] px-2 py-0.5 text-xs font-medium text-[#DC2626]">Failed</span>;
      case "GENERATING":
      case "QUEUED":
        return <span className="inline-flex items-center rounded-full bg-[#F3E8FF] px-2 py-0.5 text-xs font-medium text-[#7C3AED]">Generating...</span>;
      default:
        return <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">{status}</span>;
    }
  };

  return (
    <div className="flex items-center justify-between p-4 border-b border-[#DCE6F0] hover:bg-[#F7F9FC] transition-colors last:border-b-0">
      <div className="flex items-start gap-4">
        <div className={cn(
          "flex items-center justify-center h-10 w-10 rounded-lg shrink-0",
          currentReport.format === "PDF" ? "bg-rose-100 text-rose-600" : "bg-emerald-100 text-emerald-600"
        )}>
          <FileText className="h-5 w-5" />
        </div>
        
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-[#0F2747]">
              {currentReport.format} Report
            </span>
            {getStatusBadge(currentReport.status)}
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 text-xs text-[#58708F]">
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              Generated {formatDate(currentReport.created_at)}
            </span>
            {currentReport.error && (
              <span className="text-red-500 max-w-xs truncate">
                Error: {typeof currentReport.error === 'string' ? currentReport.error : 'Generation failed'}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="shrink-0 ml-4">
        <Button
          variant="outline"
          size="sm"
          onClick={handleDownload}
          disabled={currentReport.status !== "COMPLETED" || isDownloading || !currentReport.download_url}
          className="gap-2 bg-white"
        >
          {isDownloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          <span className="hidden sm:inline">Download</span>
        </Button>
      </div>
    </div>
  );
}

interface ReportHistoryListProps {
  projectId: string;
}

export function ReportHistoryList({ projectId }: ReportHistoryListProps) {
  const { data: reports, isLoading } = useProjectReports(projectId);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-[#DCE6F0] shadow-2xs overflow-hidden">
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-4 border-b border-[#DCE6F0]">
            <div className="flex items-center gap-4">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-48" />
              </div>
              <Skeleton className="h-9 w-24 rounded-md" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!reports || reports.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-[#DCE6F0] shadow-2xs p-8 text-center flex flex-col items-center justify-center">
        <div className="h-12 w-12 rounded-full bg-[#F7F9FC] flex items-center justify-center mb-4">
          <FileText className="h-6 w-6 text-[#58708F]" />
        </div>
        <h3 className="text-sm font-semibold text-[#0F2747] mb-1">No reports generated yet</h3>
        <p className="text-xs text-[#58708F] max-w-sm mx-auto">
          Generated PDF reports will appear here. You can download them at any time or generate a new one using the button above.
        </p>
      </div>
    );
  }

  // Sort reports by created_at desc
  const sortedReports = [...reports].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-bold text-[#0F2747] uppercase tracking-wider ml-1">
        Generated Reports
      </h3>
      <div className="bg-white rounded-xl border border-[#DCE6F0] shadow-2xs overflow-hidden">
        {sortedReports.map((report) => (
          <ReportRow key={report.id} report={report} />
        ))}
      </div>
    </div>
  );
}

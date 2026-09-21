"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { useProjects } from "@/lib/hooks/use-projects";
import { useCrossCheck } from "@/lib/hooks/use-crosscheck";
import { useMutation, useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/lib/api/endpoints";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/feedback/empty-state";
import { getStoredAuthToken } from "@/lib/api/client";
import { 
  FileSpreadsheet, 
  FileText, 
  Download, 
  Sparkles, 
  FolderKanban, 
  CheckCircle2, 
  Clock, 
  AlertCircle,
  FileCheck2,
  ArrowRight,
  Loader2
} from "lucide-react";

export default function ReportsAndExportsPage() {
  const router = useRouter();
  const { data: projects, isLoading: isProjectsLoading } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [isDownloadingCsv, setIsDownloadingCsv] = useState(false);
  const [downloadingReportId, setDownloadingReportId] = useState<string | null>(null);

  const activeProjectId = selectedProjectId || (projects && projects.length > 0 ? projects[0].id : null);
  const activeProject = projects?.find((p) => p.id === activeProjectId) || null;

  const { data: crosscheck, isLoading: isCrossCheckLoading } = useCrossCheck(activeProjectId || undefined);

  // Fetch reports for active project
  const {
    data: reports,
    isLoading: isReportsLoading,
    refetch: refetchReports,
  } = useQuery({
    queryKey: ["projects", activeProjectId, "reports"],
    queryFn: async () => {
      if (!activeProjectId) return [];
      return await reportsApi.list(activeProjectId);
    },
    enabled: !!activeProjectId,
  });

  const handleDownloadPdf = async (reportId?: string) => {
    if (!activeProjectId) return;
    if (reportId) {
      setDownloadingReportId(reportId);
    } else {
      setIsGeneratingPdf(true);
    }

    try {
      const pdfUrl = reportsApi.downloadPdfUrl(activeProjectId);
      const token = getStoredAuthToken();
      const res = await fetch(pdfUrl, {
        headers: {
          Authorization: token ? `Bearer ${token}` : "",
        },
      });
      if (!res.ok) throw new Error("Failed to generate PDF");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${activeProject?.name || "project"}_audit_report.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      refetchReports();
    } catch (err) {
      console.error("Failed to generate/download PDF", err);
    } finally {
      setIsGeneratingPdf(false);
      setDownloadingReportId(null);
    }
  };

  const handleDownloadCsv = async (reportId?: string) => {
    if (!activeProjectId) return;
    if (reportId) {
      setDownloadingReportId(reportId);
    } else {
      setIsDownloadingCsv(true);
    }

    try {
      const csvUrl = reportsApi.downloadCsvUrl(activeProjectId);
      const token = getStoredAuthToken();
      const res = await fetch(csvUrl, {
        headers: {
          Authorization: token ? `Bearer ${token}` : "",
        },
      });
      if (!res.ok) throw new Error("Failed to download CSV");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${activeProject?.name || "project"}_discrepancies.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error("Failed to download CSV", err);
    } finally {
      setIsDownloadingCsv(false);
      setDownloadingReportId(null);
    }
  };

  if (isProjectsLoading) {
    return (
      <div className="space-y-6 pb-12">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  }

  if (!projects || projects.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Reports & Exports"
          description="Generate and download audit-ready PDF summary reports and deterministic CSV discrepancy exports."
        />
        <EmptyState
          icon={FileSpreadsheet}
          title="No Projects Available"
          description="Create a project and run cross-checking to generate audit-ready summary reports and data exports."
          actionLabel="View Projects"
          onAction={() => router.push("/projects")}
        />
      </div>
    );
  }

  const isProjectReady = activeProject?.status === "COMPLETED" || activeProject?.status === "REVIEW_REQUIRED" || activeProject?.status === "FINALIZED";

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader
          title="Reports & Exports"
          description="Generate audit-ready PDF discrepancy dossiers, summary certificates, and tabular CSV data."
        />
        {activeProject && (
          <Link
            href={`/projects/${activeProject.id}`}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-white border border-[#E2E8F0] hover:border-[#CBD5E1] text-[#0F2747] shadow-sm transition-all shrink-0"
          >
            <span>Project Details</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>

      {/* Project Selector */}
      <div className="space-y-2">
        <label className="text-xs font-bold text-[#58708F] uppercase tracking-wider">
          Active Project
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {projects.map((proj) => {
            const isSelected = proj.id === activeProjectId;
            return (
              <button
                key={proj.id}
                type="button"
                onClick={() => setSelectedProjectId(proj.id)}
                className={`flex flex-col text-left p-3.5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? "bg-white border-[#0EA5E9] ring-2 ring-[#0EA5E9]/20 shadow-sm"
                    : "bg-white/60 hover:bg-white border-[#E2E8F0] hover:border-[#CBD5E1]"
                }`}
              >
                <div className="flex items-center justify-between gap-2 w-full">
                  <div className="flex items-center gap-2 truncate">
                    <FolderKanban className={`h-4 w-4 shrink-0 ${isSelected ? "text-[#0EA5E9]" : "text-[#58708F]"}`} />
                    <span className="font-semibold text-sm text-[#0F2747] truncate">
                      {proj.name}
                    </span>
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                    {proj.status.replace("_", " ")}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Export Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* CSV Tabular Export Card */}
        <div className="bg-white rounded-2xl border border-[#E2E8F0] p-6 shadow-sm flex flex-col justify-between space-y-5 hover:border-[#0EA5E9]/50 transition-colors">
          <div className="space-y-3">
            <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
              <FileSpreadsheet className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#0F2747]">
                Deterministic CSV Discrepancy Export
              </h3>
              <p className="text-xs text-[#58708F] mt-1 leading-relaxed">
                Download raw tabular discrepancy metrics, line items, design vs order dimensions, and manufacturer statuses directly into Excel / CSV format.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <span className="text-xs text-[#58708F]">
              Format: <strong className="text-[#0F2747]">.CSV (UTF-8)</strong>
            </span>
            <button
              type="button"
              disabled={!isProjectReady || isDownloadingCsv}
              onClick={() => handleDownloadCsv()}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 disabled:opacity-50 cursor-pointer"
            >
              {isDownloadingCsv ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Downloading CSV...</span>
                </>
              ) : (
                <>
                  <Download className="h-4 w-4" />
                  <span>Download CSV File</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* PDF Audit Dossier Card */}
        <div className="bg-white rounded-2xl border border-[#E2E8F0] p-6 shadow-sm flex flex-col justify-between space-y-5 hover:border-[#0EA5E9]/50 transition-colors">
          <div className="space-y-3">
            <div className="w-12 h-12 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
              <FileText className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#0F2747]">
                Audit-Ready PDF Dossier
              </h3>
              <p className="text-xs text-[#58708F] mt-1 leading-relaxed">
                Generate and download an instant multi-page executive audit dossier complete with 3-way reconciliation matrices, variance logs, and signature blocks.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <span className="text-xs text-[#58708F]">
              Format: <strong className="text-[#0F2747]">.PDF (Instant Download)</strong>
            </span>
            <button
              type="button"
              disabled={!isProjectReady || isGeneratingPdf}
              onClick={() => handleDownloadPdf()}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-[#0EA5E9] hover:bg-[#0284C7] text-white shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/50 disabled:opacity-50 cursor-pointer"
            >
              {isGeneratingPdf ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Downloading PDF...</span>
                </>
              ) : (
                <>
                  <Download className="h-4 w-4" />
                  <span>Download PDF Report</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Generated Reports Table */}
      <div className="bg-white rounded-2xl border border-[#E2E8F0] overflow-hidden shadow-sm">
        <div className="p-5 border-b border-[#E2E8F0] flex items-center justify-between">
          <h3 className="text-sm font-bold text-[#0F2747] flex items-center gap-2">
            <FileCheck2 className="h-4 w-4 text-[#0EA5E9]" />
            Generated Reports History for {activeProject?.name}
          </h3>
          <button
            type="button"
            onClick={() => refetchReports()}
            className="text-xs font-semibold text-[#58708F] hover:text-[#0F2747] cursor-pointer"
          >
            Refresh
          </button>
        </div>

        {isReportsLoading ? (
          <div className="p-6 space-y-3">
            <Skeleton className="h-10 rounded-lg" />
            <Skeleton className="h-10 rounded-lg" />
          </div>
        ) : reports && reports.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {reports.map((rep) => {
              const isItemDownloading = downloadingReportId === rep.id;
              return (
                <div
                  key={rep.id}
                  className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/60 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center text-[#0EA5E9]">
                      {rep.format === "PDF" ? <FileText className="h-4 w-4" /> : <FileSpreadsheet className="h-4 w-4" />}
                    </div>
                    <div>
                      <h5 className="text-xs font-bold text-[#0F2747]">
                        {activeProject?.name} — {rep.format} Summary Report
                      </h5>
                      <p className="text-[11px] text-[#58708F]">
                        Created: {new Date(rep.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-auto">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        rep.status === "COMPLETED"
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : rep.status === "GENERATING" || rep.status === "QUEUED"
                          ? "bg-blue-50 text-blue-700 border border-blue-200"
                          : "bg-rose-50 text-rose-700 border border-rose-200"
                      }`}
                    >
                      {rep.status}
                    </span>

                    <button
                      type="button"
                      disabled={isItemDownloading}
                      onClick={() => rep.format === "PDF" ? handleDownloadPdf(rep.id) : handleDownloadCsv(rep.id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-[#0F2747] transition-colors cursor-pointer disabled:opacity-50"
                    >
                      {isItemDownloading ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-[#0EA5E9]" />
                          <span>Downloading...</span>
                        </>
                      ) : (
                        <>
                          <Download className="h-3.5 w-3.5" />
                          <span>Download</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="p-8 text-center text-xs text-[#58708F]">
            No PDF/CSV reports have been archived yet for this project. Click above to generate or download.
          </div>
        )}
      </div>
    </div>
  );
}


"use client";

import React, { use, useState, useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { useProject } from "@/lib/hooks/use-projects";
import { useCrossCheck } from "@/lib/hooks/use-crosscheck";
import { useCrossCheckConfig } from "@/lib/hooks/use-crosscheck-preferences";
import { useFinalizeProject } from "@/lib/hooks/use-reviews";
import { useAuthStore } from "@/lib/store/auth-store";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/feedback/error-state";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ReviewSummary } from "@/components/review/review-summary";
import { ReviewFilters } from "@/components/review/review-filters";
import { ReviewList } from "@/components/review/review-list";
import { ReviewDetailDrawer } from "@/components/review/review-detail-drawer";
import { Discrepancy, MatchGroup } from "@/lib/api/types";
import { FinalizeProjectDialog } from "@/components/projects/finalize-project-dialog";

export default function ReviewPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const resolvedParams = use(params);
  const projectId = resolvedParams.projectId;

  const { profile } = useAuthStore();
  const canManage = profile?.role === "ADMIN" || profile?.role === "REVIEWER";

  const {
    data: project,
    isLoading: isProjectLoading,
    error: projectError,
  } = useProject(projectId);

  const {
    data: crosscheck,
    isLoading: isCrossCheckLoading,
    error: crossCheckError,
    refetch,
  } = useCrossCheck(projectId);

  const { config: crossCheckConfig } = useCrossCheckConfig();

  const [selectedDiscrepancyId, setSelectedDiscrepancyId] = useState<string | null>(null);
  const [finalizeDialogOpen, setFinalizeDialogOpen] = useState(false);

  // Filters State
  const [statusFilter, setStatusFilter] = useState<string>("All");
  const [severityFilter, setSeverityFilter] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState("");

  const isFinalized = project?.status === "FINALIZED";

  // Flatten and filter discrepancies
  const discrepanciesWithGroup = useMemo(() => {
    if (!crosscheck) return [];
    
    return crosscheck.groups.flatMap(group => 
      group.discrepancies.map(d => ({
        ...d,
        group
      }))
    );
  }, [crosscheck]);

  const filteredDiscrepancies = useMemo(() => {
    const list = discrepanciesWithGroup.filter(d => {
      // Filter by Status
      if (statusFilter !== "All" && d.status !== statusFilter) return false;
      
      // Filter by Severity
      if (severityFilter !== "All" && d.severity !== severityFilter) return false;
      
      // Filter by Search
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesSku = (d.group.canonical_sku || "").toLowerCase().includes(query);
        const matchesField = (d.field_name || "").toLowerCase().includes(query);
        const matchesDesign = (d.design_value || "").toLowerCase().includes(query);
        const matchesOrder = (d.order_value || "").toLowerCase().includes(query);
        const matchesAck = (d.ack_value || "").toLowerCase().includes(query);
        
        if (!matchesSku && !matchesField && !matchesDesign && !matchesOrder && !matchesAck) {
          return false;
        }
      }
      
      return true;
    });

    // Apply Live Workspace Preference: Highlight Critical First
    if (crossCheckConfig.highlightCriticalFirst) {
      const severityOrder: Record<string, number> = {
        CRITICAL: 1,
        HIGH: 2,
        WARNING: 3,
        INFO: 4,
      };
      return [...list].sort((a, b) => {
        const orderA = severityOrder[a.severity] || 5;
        const orderB = severityOrder[b.severity] || 5;
        return orderA - orderB;
      });
    }

    return list;
  }, [discrepanciesWithGroup, statusFilter, severityFilter, searchQuery, crossCheckConfig.highlightCriticalFirst]);

  if (isProjectLoading || isCrossCheckLoading) {
    return (
      <div className="space-y-6 pb-12">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  }

  if (projectError || crossCheckError || !project || !crosscheck) {
    return (
      <div className="space-y-6 pb-12">
        <Link
          href={`/projects/${projectId}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#58708F] hover:text-[#0F2747]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Project
        </Link>
        <ErrorState
          title="Could not load Review Data"
          message="There was an error loading the review data for this project."
          onRetry={refetch}
        />
      </div>
    );
  }

  const selectedDiscrepancy = discrepanciesWithGroup.find(d => d.id === selectedDiscrepancyId) || null;

  return (
    <div className="space-y-6 pb-12 relative">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <Link
            href={`/projects/${projectId}/crosscheck`}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#58708F] hover:text-[#0F2747] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/30 rounded-md py-1 px-1.5 -ml-1.5"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Cross-Check Matrix</span>
          </Link>
          <h1 className="mt-2 text-xl sm:text-2xl font-bold text-[#0F2747] tracking-tight flex items-center gap-2">
            Human Review
            {isFinalized && (
              <span className="text-xs font-bold bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md uppercase tracking-wider">
                Finalized (Read Only)
              </span>
            )}
          </h1>
          <p className="text-sm text-[#58708F]">
            Project: {project.name}
          </p>
        </div>

        {canManage && !isFinalized && (
          <Button 
            className="bg-[#16A34A] hover:bg-[#15803D] text-white font-semibold shadow-xs"
            onClick={() => setFinalizeDialogOpen(true)}
            leftIcon={<CheckCircle2 className="h-4 w-4" />}
          >
            Finalize Project
          </Button>
        )}
      </div>

      <ReviewSummary discrepancies={discrepanciesWithGroup} />

      <div className="bg-white border border-[#DCE6F0] rounded-xl shadow-2xs overflow-hidden">
        <ReviewFilters 
          statusFilter={statusFilter}
          onStatusChange={setStatusFilter}
          severityFilter={severityFilter}
          onSeverityChange={setSeverityFilter}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />
        <ReviewList 
          discrepancies={filteredDiscrepancies} 
          onSelect={setSelectedDiscrepancyId} 
        />
      </div>

      <ReviewDetailDrawer 
        discrepancy={selectedDiscrepancy}
        group={selectedDiscrepancy?.group || null}
        projectId={projectId}
        isOpen={!!selectedDiscrepancyId}
        onClose={() => setSelectedDiscrepancyId(null)}
        readOnly={!canManage || isFinalized}
      />

      <FinalizeProjectDialog 
        projectId={projectId}
        isOpen={finalizeDialogOpen}
        onClose={() => setFinalizeDialogOpen(false)}
      />
    </div>
  );
}

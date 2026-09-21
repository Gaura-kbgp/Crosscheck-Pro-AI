"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useCrossCheck } from "@/lib/hooks/use-crosscheck";
import { useProject } from "@/lib/hooks/use-projects";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/feedback/error-state";
import { CrossCheckSummary } from "@/components/crosscheck/crosscheck-summary";
import { CrossCheckList } from "@/components/crosscheck/crosscheck-list";
import { MatchGroupDetailDrawer } from "@/components/crosscheck/match-group-detail-drawer";

export default function CrossCheckPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const resolvedParams = use(params);
  const projectId = resolvedParams.projectId;

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

  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<string | null>(null);

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
          title="Could not load Cross-Check Results"
          message="There was an error loading the verification results for this project."
          onRetry={refetch}
        />
      </div>
    );
  }

  const selectedGroup = crosscheck.groups.find((g) => g.id === selectedGroupId) || null;

  return (
    <div className="space-y-6 pb-12 relative">
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#58708F] hover:text-[#0F2747] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/30 rounded-md py-1 px-1.5 -ml-1.5"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Project</span>
        </Link>
        <h1 className="mt-2 text-xl sm:text-2xl font-bold text-[#0F2747] tracking-tight">
          Cross-Check Results
        </h1>
        <p className="text-sm text-[#58708F]">
          Project: {project.name}
        </p>
      </div>

      <CrossCheckSummary
        summary={crosscheck.summary}
        selectedFilter={selectedFilter}
        onSelectFilter={setSelectedFilter}
      />

      <CrossCheckList
        groups={crosscheck.groups}
        filterStatus={selectedFilter}
        onSelectGroup={(id) => setSelectedGroupId(id)}
        onClearFilter={() => setSelectedFilter(null)}
      />

      <MatchGroupDetailDrawer
        group={selectedGroup}
        isOpen={!!selectedGroup}
        onClose={() => setSelectedGroupId(null)}
      />
    </div>
  );
}


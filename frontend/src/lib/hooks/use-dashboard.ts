import { useMemo } from "react";
import { useProjects } from "./use-projects";
import { Project } from "@/lib/api/types";

export interface DashboardMetrics {
  totalProjects: number;
  processingCount: number;
  needsReviewCount: number;
  completedCount: number;
  draftCount: number;
  recentProjects: Project[];
  hasProjects: boolean;
}

export interface ActivityDataPoint {
  date: string;
  formattedDate: string;
  count: number;
}

export function useDashboard(timeframeDays: 7 | 30 = 7) {
  const { data: projects, isLoading, error, refetch, isFetching } = useProjects();

  const metrics: DashboardMetrics = useMemo(() => {
    if (!projects || projects.length === 0) {
      return {
        totalProjects: 0,
        processingCount: 0,
        needsReviewCount: 0,
        completedCount: 0,
        draftCount: 0,
        recentProjects: [],
        hasProjects: false,
      };
    }

    const totalProjects = projects.length;
    let processingCount = 0;
    let needsReviewCount = 0;
    let completedCount = 0;
    let draftCount = 0;

    projects.forEach((project) => {
      switch (project.status) {
        case "PROCESSING":
          processingCount++;
          break;
        case "REVIEW_REQUIRED":
          needsReviewCount++;
          break;
        case "COMPLETED":
        case "FINALIZED":
          completedCount++;
          break;
        case "DRAFT":
          draftCount++;
          break;
      }
    });

    // Sort recent projects by updated_at descending
    const sortedProjects = [...projects].sort(
      (a, b) =>
        new Date(b.updated_at || b.created_at).getTime() -
        new Date(a.updated_at || a.created_at).getTime()
    );

    return {
      totalProjects,
      processingCount,
      needsReviewCount,
      completedCount,
      draftCount,
      recentProjects: sortedProjects.slice(0, 5),
      hasProjects: totalProjects > 0,
    };
  }, [projects]);

  // Compute activity metrics for the requested timeframe (last 7 or 30 days)
  const activityData: ActivityDataPoint[] = useMemo(() => {
    if (!projects || projects.length === 0) {
      return [];
    }

    const now = new Date();
    const days: ActivityDataPoint[] = [];

    for (let i = timeframeDays - 1; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split("T")[0];
      const formattedDate = new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
      }).format(d);

      days.push({
        date: dateStr,
        formattedDate,
        count: 0,
      });
    }

    const dateMap = new Map<string, number>();
    days.forEach((day) => dateMap.set(day.date, 0));

    projects.forEach((p) => {
      const updatedDate = (p.updated_at || p.created_at).split("T")[0];
      if (dateMap.has(updatedDate)) {
        dateMap.set(updatedDate, (dateMap.get(updatedDate) || 0) + 1);
      }
    });

    return days.map((day) => ({
      ...day,
      count: dateMap.get(day.date) || 0,
    }));
  }, [projects, timeframeDays]);

  const hasActivity = useMemo(
    () => activityData.some((point) => point.count > 0),
    [activityData]
  );

  return {
    metrics,
    activityData,
    hasActivity,
    isLoading,
    isFetching,
    error,
    refetch,
  };
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { reviewApi } from "../api/endpoints";
import { ReviewActionRequest } from "../api/types";

export function useReviewAction(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ discrepancyId, data }: { discrepancyId: string; data: ReviewActionRequest }) => {
      const response = await reviewApi.submitAction(discrepancyId, data);
      return response;
    },
    onSuccess: () => {
      // Invalidate relevant queries to fetch fresh data
      queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "crosscheck"] });
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "audit-logs"] });
    },
  });
}

export function useBulkAcceptNonCritical(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (reason?: string) => {
      const response = await reviewApi.bulkAcceptNonCritical(projectId, reason);
      return response;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "crosscheck"] });
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "audit-logs"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useFinalizeProject(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const response = await reviewApi.finalize(projectId);
      return response;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useAuditLogs(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "audit-logs"],
    queryFn: async () => {
      if (!projectId) throw new Error("Project ID is required");
      const data = await reviewApi.getAuditLogs(projectId);
      return data;
    },
    enabled: !!projectId,
  });
}

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { reportsApi } from "../api/endpoints";
import { getStoredAuthToken } from "../api/client";

export function useProjectReports(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "reports"],
    queryFn: async () => {
      if (!projectId) throw new Error("Project ID is required");
      const data = await reportsApi.list(projectId);
      return data;
    },
    enabled: !!projectId,
  });
}

export function useGenerateReport(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ format = "PDF" }: { format?: string }) => {
      const response = await reportsApi.create(projectId, { format });
      return response;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "reports"] });
    },
  });
}

export function useReportStatus(reportId: string | null, enabled: boolean = true) {
  return useQuery({
    queryKey: ["reports", reportId, "status"],
    queryFn: async () => {
      if (!reportId) throw new Error("Report ID is required");
      const data = await reportsApi.status(reportId);
      return data;
    },
    enabled: !!reportId && enabled,
    refetchInterval: (query) => {
      // Poll every 3 seconds if status is QUEUED or GENERATING
      const data = query.state.data;
      if (data?.status === "QUEUED" || data?.status === "GENERATING") {
        return 3000;
      }
      return false; // Stop polling
    },
  });
}

export function useDownloadCsv(projectId: string) {
  return () => {
    const url = reportsApi.downloadCsvUrl(projectId);
    const token = getStoredAuthToken();
    
    // We can fetch it to include the Authorization header, then trigger a download via blob
    return fetch(url, {
      headers: {
        "Authorization": token ? `Bearer ${token}` : "",
      },
    })
    .then(res => {
      if (!res.ok) throw new Error("Failed to download CSV");
      return res.blob();
    })
    .then(blob => {
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `project_${projectId}_crosscheck.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    });
  };
}

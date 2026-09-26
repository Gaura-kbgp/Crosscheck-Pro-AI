import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { documentsApi, processingApi } from "@/lib/api/endpoints";
import { DocumentType, ProcessingJobResponse } from "@/lib/api/types";
import { PROJECT_KEYS } from "./use-projects";

const ACCEPTED_DOCUMENT_EXTENSIONS = [
  ".pdf",
  ".jpg",
  ".jpeg",
  ".png",
  ".gif",
  ".bmp",
  ".webp",
  ".tif",
  ".tiff",
  ".xls",
  ".xlsx",
  ".csv",
  ".txt",
  ".md",
  ".doc",
  ".docx",
];

export const DOCUMENT_KEYS = {
  all: ["documents"] as const,
  projectDocuments: (projectId: string) => [...DOCUMENT_KEYS.all, "project", projectId] as const,
  documentUrl: (projectId: string, documentId: string) =>
    [...DOCUMENT_KEYS.all, "url", projectId, documentId] as const,
  jobStatus: (jobId: string) => ["processing", "job", jobId] as const,
};

export function useProjectDocuments(projectId: string) {
  return useQuery({
    queryKey: DOCUMENT_KEYS.projectDocuments(projectId),
    queryFn: () => documentsApi.list(projectId),
    enabled: Boolean(projectId),
    staleTime: 1000 * 10, // 10 seconds
  });
}

export function useUploadDocument(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      documentType,
      file,
    }: {
      documentType: DocumentType;
      file: File;
    }) => {
      // Validate file size (< 10 MB)
      const maxSizeBytes = 200 * 1024 * 1024;
      if (file.size > maxSizeBytes) {
        throw new Error("File exceeds the maximum limit of 200 MB.");
      }
      // Validate file extension / MIME
      const lowerName = file.name.toLowerCase();
      const isAccepted = ACCEPTED_DOCUMENT_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
      if (!isAccepted) {
        throw new Error("Unsupported file format. Please upload a PDF, image, or Excel/CSV file.");
      }
      return documentsApi.upload(projectId, documentType, file);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: DOCUMENT_KEYS.projectDocuments(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: PROJECT_KEYS.detail(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: PROJECT_KEYS.lists(),
      });
    },
  });
}

export function useDeleteDocument(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => documentsApi.delete(projectId, documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: DOCUMENT_KEYS.projectDocuments(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: PROJECT_KEYS.detail(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: PROJECT_KEYS.lists(),
      });
    },
  });
}

export function useStartProcessing(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => processingApi.start(projectId),
    onSuccess: (job: ProcessingJobResponse) => {
      queryClient.invalidateQueries({
        queryKey: PROJECT_KEYS.detail(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: DOCUMENT_KEYS.projectDocuments(projectId),
      });
      return job;
    },
  });
}

export function useJobStatus(jobId: string | null, enabled: boolean = true) {
  return useQuery({
    queryKey: DOCUMENT_KEYS.jobStatus(jobId || ""),
    queryFn: () => {
      if (!jobId) throw new Error("Job ID required");
      return processingApi.jobStatus(jobId);
    },
    enabled: Boolean(jobId) && enabled,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2000;
      // Stop polling on terminal states
      if (data.status === "COMPLETED" || data.status === "FAILED") {
        return false;
      }
      return 2000; // Poll every 2s during active processing
    },
    staleTime: 0,
  });
}

export function useLatestJob(projectId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: [...DOCUMENT_KEYS.all, "latestJob", projectId],
    queryFn: () => processingApi.latestJob(projectId),
    enabled: Boolean(projectId) && enabled,
    retry: false,
    staleTime: 0,
  });
}

export function useCancelJob(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) => processingApi.cancel(jobId),
    onSuccess: (job: ProcessingJobResponse) => {
      queryClient.invalidateQueries({
        queryKey: DOCUMENT_KEYS.jobStatus(job.id),
      });
      queryClient.invalidateQueries({
        queryKey: PROJECT_KEYS.detail(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: DOCUMENT_KEYS.projectDocuments(projectId),
      });
      return job;
    },
  });
}

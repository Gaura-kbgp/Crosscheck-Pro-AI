import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { nkbaReferenceApi } from "@/lib/api/endpoints";

export const NKBA_REFERENCE_KEYS = {
  all: ["nkba-reference-documents"] as const,
};

export function useNKBAReferenceDocuments() {
  return useQuery({
    queryKey: NKBA_REFERENCE_KEYS.all,
    queryFn: () => nkbaReferenceApi.list(),
    staleTime: 1000 * 30,
  });
}

export function useUploadNKBAReferenceDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, label }: { file: File; label: string }) => nkbaReferenceApi.upload(file, label),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NKBA_REFERENCE_KEYS.all });
    },
  });
}

export function useDeleteNKBAReferenceDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => nkbaReferenceApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NKBA_REFERENCE_KEYS.all });
    },
  });
}

export function useNKBAReferenceDownloadUrl() {
  return useMutation({
    mutationFn: (id: string) => nkbaReferenceApi.getDownloadUrl(id),
  });
}

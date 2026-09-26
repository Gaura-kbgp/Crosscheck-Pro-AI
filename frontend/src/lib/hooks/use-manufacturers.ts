import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { manufacturersApi } from "@/lib/api/endpoints";
import {
  ManufacturerCreateInput,
  ManufacturerUpdateInput,
  ManufacturerCodeCreateInput,
  ManufacturerCodeUpdateInput,
  SpecBookRowStatus,
  SpecBookRowUpdateInput,
  ApproveRowsRequest,
} from "@/lib/api/types";

export const MANUFACTURER_KEYS = {
  all: ["manufacturers"] as const,
  lists: () => [...MANUFACTURER_KEYS.all, "list"] as const,
  codes: (manufacturerId: string, params?: { search?: string; category?: string }) =>
    [...MANUFACTURER_KEYS.all, manufacturerId, "codes", params ?? {}] as const,
  specBooks: (manufacturerId: string) => [...MANUFACTURER_KEYS.all, manufacturerId, "spec-books"] as const,
  specBook: (manufacturerId: string, bookId: string) => [...MANUFACTURER_KEYS.all, manufacturerId, "spec-books", bookId] as const,
  specBookRows: (manufacturerId: string, bookId: string, status?: SpecBookRowStatus) =>
    [...MANUFACTURER_KEYS.all, manufacturerId, "spec-books", bookId, "rows", status ?? "all"] as const,
};

export function useManufacturers() {
  return useQuery({
    queryKey: MANUFACTURER_KEYS.lists(),
    queryFn: () => manufacturersApi.list(),
    staleTime: 1000 * 30,
  });
}

export function useCreateManufacturer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ManufacturerCreateInput) => manufacturersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MANUFACTURER_KEYS.lists() });
    },
  });
}

export function useUpdateManufacturer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ManufacturerUpdateInput }) =>
      manufacturersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MANUFACTURER_KEYS.lists() });
    },
  });
}

export function useManufacturerCodes(manufacturerId: string | null, params?: { search?: string; category?: string }) {
  return useQuery({
    queryKey: MANUFACTURER_KEYS.codes(manufacturerId ?? "", params),
    queryFn: () => manufacturersApi.listCodes(manufacturerId as string, params),
    enabled: !!manufacturerId,
    staleTime: 1000 * 15,
  });
}

export function useCreateManufacturerCode(manufacturerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ManufacturerCodeCreateInput) => manufacturersApi.createCode(manufacturerId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...MANUFACTURER_KEYS.all, manufacturerId, "codes"] });
    },
  });
}

export function useUpdateManufacturerCode(manufacturerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ codeId, data }: { codeId: string; data: ManufacturerCodeUpdateInput }) =>
      manufacturersApi.updateCode(manufacturerId, codeId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...MANUFACTURER_KEYS.all, manufacturerId, "codes"] });
    },
  });
}

export function useDeactivateManufacturerCode(manufacturerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (codeId: string) => manufacturersApi.deactivateCode(manufacturerId, codeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...MANUFACTURER_KEYS.all, manufacturerId, "codes"] });
    },
  });
}

export function useDeleteManufacturerCode(manufacturerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (codeId: string) => manufacturersApi.deleteCode(manufacturerId, codeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...MANUFACTURER_KEYS.all, manufacturerId, "codes"] });
    },
  });
}

export function usePreviewImport(manufacturerId: string) {
  return useMutation({
    mutationFn: (file: File) => manufacturersApi.previewImport(manufacturerId, file),
  });
}

export function useCommitImport(manufacturerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => manufacturersApi.commitImport(manufacturerId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...MANUFACTURER_KEYS.all, manufacturerId, "codes"] });
    },
  });
}

// ---- Specification Book: Upload -> Extract -> Review -> Approve ----------

export function useSpecBooks(manufacturerId: string | null) {
  return useQuery({
    queryKey: MANUFACTURER_KEYS.specBooks(manufacturerId ?? ""),
    queryFn: () => manufacturersApi.listSpecBooks(manufacturerId as string),
    enabled: !!manufacturerId,
    staleTime: 1000 * 10,
  });
}

export function useSpecBook(manufacturerId: string | null, bookId: string | null, opts?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: MANUFACTURER_KEYS.specBook(manufacturerId ?? "", bookId ?? ""),
    queryFn: () => manufacturersApi.getSpecBook(manufacturerId as string, bookId as string),
    enabled: !!manufacturerId && !!bookId,
    refetchInterval: opts?.refetchInterval,
  });
}

export function useUploadSpecBook(manufacturerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, sourceVersion }: { file: File; sourceVersion?: string }) =>
      manufacturersApi.uploadSpecBook(manufacturerId, file, sourceVersion),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MANUFACTURER_KEYS.specBooks(manufacturerId) });
    },
  });
}

export function useSpecBookRows(manufacturerId: string | null, bookId: string | null, status?: SpecBookRowStatus) {
  return useQuery({
    queryKey: MANUFACTURER_KEYS.specBookRows(manufacturerId ?? "", bookId ?? "", status),
    queryFn: () => manufacturersApi.listSpecBookRows(manufacturerId as string, bookId as string, status),
    enabled: !!manufacturerId && !!bookId,
  });
}

export function useUpdateSpecBookRow(manufacturerId: string, bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rowId, data }: { rowId: string; data: SpecBookRowUpdateInput }) =>
      manufacturersApi.updateSpecBookRow(manufacturerId, bookId, rowId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...MANUFACTURER_KEYS.all, manufacturerId, "spec-books", bookId, "rows"] });
    },
  });
}

export function useRejectSpecBookRow(manufacturerId: string, bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rowId: string) => manufacturersApi.rejectSpecBookRow(manufacturerId, bookId, rowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...MANUFACTURER_KEYS.all, manufacturerId, "spec-books", bookId, "rows"] });
    },
  });
}

export function useApproveSpecBookRows(manufacturerId: string, bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ApproveRowsRequest) => manufacturersApi.approveSpecBookRows(manufacturerId, bookId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...MANUFACTURER_KEYS.all, manufacturerId, "spec-books", bookId, "rows"] });
      queryClient.invalidateQueries({ queryKey: [...MANUFACTURER_KEYS.all, manufacturerId, "codes"] });
    },
  });
}

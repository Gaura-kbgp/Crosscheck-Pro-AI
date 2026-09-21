import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "@/lib/api/endpoints";
import { Project, ProjectCreateInput, ProjectUpdateInput } from "@/lib/api/types";

export const PROJECT_KEYS = {
  all: ["projects"] as const,
  lists: () => [...PROJECT_KEYS.all, "list"] as const,
  detail: (id: string) => [...PROJECT_KEYS.all, "detail", id] as const,
};

export function useProjects() {
  return useQuery({
    queryKey: PROJECT_KEYS.lists(),
    queryFn: () => projectsApi.list(),
    staleTime: 1000 * 30, // 30 seconds
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: PROJECT_KEYS.detail(id),
    queryFn: () => projectsApi.get(id),
    enabled: !!id,
    staleTime: 1000 * 30,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProjectCreateInput) => projectsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROJECT_KEYS.lists() });
    },
  });
}

export function useUpdateProject(id?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id: targetId, data }: { id?: string; data: ProjectUpdateInput }) => {
      const finalId = targetId || id;
      if (!finalId) throw new Error("Project ID is required");
      return projectsApi.update(finalId, data);
    },
    onSuccess: (updatedProject: Project) => {
      queryClient.setQueryData(PROJECT_KEYS.detail(updatedProject.id), updatedProject);
      queryClient.invalidateQueries({ queryKey: PROJECT_KEYS.lists() });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => projectsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROJECT_KEYS.lists() });
    },
  });
}

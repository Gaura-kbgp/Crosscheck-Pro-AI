import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { organizationsApi, usersApi } from "@/lib/api/endpoints";
import { Organization, OrganizationUpdateInput, UserProfile, UserUpdateInput } from "@/lib/api/types";
import { useAuthStore } from "@/lib/store/auth-store";

export const SETTINGS_KEYS = {
  organization: ["organization", "me"] as const,
  userProfile: ["users", "me"] as const,
};

export function useOrganization() {
  const { session } = useAuthStore();
  return useQuery({
    queryKey: SETTINGS_KEYS.organization,
    queryFn: () => organizationsApi.getMe(),
    enabled: !!session,
    staleTime: 1000 * 60, // 1 minute
  });
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: OrganizationUpdateInput) => organizationsApi.updateMe(data),
    onSuccess: (updatedOrg: Organization) => {
      queryClient.setQueryData(SETTINGS_KEYS.organization, updatedOrg);
    },
  });
}

export function useUserProfile() {
  const { session } = useAuthStore();
  return useQuery({
    queryKey: SETTINGS_KEYS.userProfile,
    queryFn: () => usersApi.getMe(),
    enabled: !!session,
    staleTime: 1000 * 60,
  });
}

export function useUpdateUserProfile() {
  const queryClient = useQueryClient();
  const { fetchProfile } = useAuthStore();

  return useMutation({
    mutationFn: (data: UserUpdateInput) => usersApi.updateMe(data),
    onSuccess: (updatedUser: UserProfile) => {
      queryClient.setQueryData(SETTINGS_KEYS.userProfile, updatedUser);
      fetchProfile();
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { current_password?: string; new_password: string }) =>
      usersApi.changePassword(data),
  });
}

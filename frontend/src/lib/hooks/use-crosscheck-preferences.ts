import { useMemo } from "react";
import { useOrganization, useUpdateOrganization } from "./use-organization";

export interface CrossCheckWorkspaceConfig {
  highlightCriticalFirst: boolean;
  autoAdvanceReview: boolean;
  requireReviewNoteOnOverride: boolean;
  lockProjectOnFinalize: boolean;
  dimensionToleranceInches: number; // e.g. 0.0, 0.125, 0.25
  priceVariancePercent: number; // e.g. 0, 5, 10
  quantityMismatchSeverity: "CRITICAL" | "HIGH";
  dimensionMismatchSeverity: "HIGH" | "WARNING";
}

export const DEFAULT_CROSSCHECK_CONFIG: CrossCheckWorkspaceConfig = {
  highlightCriticalFirst: true,
  autoAdvanceReview: true,
  requireReviewNoteOnOverride: true,
  lockProjectOnFinalize: true,
  dimensionToleranceInches: 0.125,
  priceVariancePercent: 5,
  quantityMismatchSeverity: "CRITICAL",
  dimensionMismatchSeverity: "WARNING",
};

const STORAGE_KEY = "crosscheck_workspace_preferences";

export function getLocalCrossCheckConfig(): CrossCheckWorkspaceConfig {
  if (typeof window === "undefined") return DEFAULT_CROSSCHECK_CONFIG;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULT_CROSSCHECK_CONFIG, ...JSON.parse(raw) } : DEFAULT_CROSSCHECK_CONFIG;
  } catch {
    return DEFAULT_CROSSCHECK_CONFIG;
  }
}

export function saveLocalCrossCheckConfig(config: CrossCheckWorkspaceConfig) {
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  }
}

export function useCrossCheckConfig() {
  const { data: organization, isLoading } = useOrganization();
  const updateOrg = useUpdateOrganization();

  const config = useMemo<CrossCheckWorkspaceConfig>(() => {
    const orgSettings = organization?.settings as Record<string, unknown> | undefined;
    const serverConfig = orgSettings?.crosscheck_preferences as Partial<CrossCheckWorkspaceConfig> | undefined;
    const local = getLocalCrossCheckConfig();

    return {
      ...DEFAULT_CROSSCHECK_CONFIG,
      ...local,
      ...(serverConfig || {}),
    };
  }, [organization?.settings]);

  const saveConfig = async (newConfig: CrossCheckWorkspaceConfig) => {
    saveLocalCrossCheckConfig(newConfig);
    if (organization?.id) {
      await updateOrg.mutateAsync({
        settings: {
          crosscheck_preferences: newConfig,
        },
      });
    }
  };

  return {
    config,
    isLoading,
    isSaving: updateOrg.isPending,
    saveConfig,
  };
}

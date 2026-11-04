"use client";

import { useEffect } from "react";

const STORAGE_KEY = "ccp_last_viewed_project_id";

/**
 * Call from a project-scoped page so the global hub pages (sidebar
 * "Cross-Check" / "Reviews") can default to THIS project next time,
 * instead of always landing on projects[0] — a user who was just looking
 * at "Demo Project" and clicks a sidebar link shouldn't be dropped into
 * an unrelated project's data with no indication why.
 */
export function useRecordLastViewedProject(projectId: string | undefined) {
  useEffect(() => {
    if (!projectId) return;
    try {
      localStorage.setItem(STORAGE_KEY, projectId);
    } catch {
      // Storage unavailable (private browsing, quota) — hub pages fall
      // back to projects[0] as before; nothing else depends on this.
    }
  }, [projectId]);
}

export function getLastViewedProjectId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

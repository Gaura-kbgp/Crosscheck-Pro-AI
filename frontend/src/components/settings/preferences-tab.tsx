"use client";

import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { LocalPreferences } from "@/lib/api/types";
import {
  Sliders,
  LayoutGrid,
  List,
  GitCompare,
  AlertTriangle,
  RotateCw,
  Check,
  Sparkles,
} from "lucide-react";

const DEFAULT_PREFERENCES: LocalPreferences = {
  defaultProjectView: "grid",
  defaultCrossCheckView: "all",
  density: "comfortable",
  confirmDestructiveActions: true,
  autoRefreshInterval: 5,
  theme: "system",
};

const PREFERENCES_STORAGE_KEY = "crosscheck_user_preferences";

export function getStoredPreferences(): LocalPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = localStorage.getItem(PREFERENCES_STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    return { ...DEFAULT_PREFERENCES, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function PreferencesTab() {
  const [preferences, setPreferences] = useState<LocalPreferences>(getStoredPreferences);
  const [isSaved, setIsSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (typeof window !== "undefined") {
      localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 3000);
    }
  };

  const updateField = <K extends keyof LocalPreferences>(
    key: K,
    value: LocalPreferences[K]
  ) => {
    setPreferences((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-[#0EA5E9]">
              <Sliders className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>Workspace Preferences</CardTitle>
              <CardDescription>
                Customize your individual workflow, visual density, and review defaults.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <form onSubmit={handleSave}>
          <CardContent className="space-y-6">
            {isSaved && (
              <Alert variant="success" title="Preferences Saved">
                Your workspace preferences have been saved locally for this browser session.
              </Alert>
            )}

            {/* Default Project View */}
            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                <LayoutGrid className="h-3.5 w-3.5 text-[#0EA5E9]" />
                Default Projects Layout
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => updateField("defaultProjectView", "grid")}
                  className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all ${
                    preferences.defaultProjectView === "grid"
                      ? "border-[#0EA5E9] bg-sky-50/50 ring-1 ring-[#0EA5E9]"
                      : "border-[#DCE6F0] bg-white hover:border-slate-300"
                  }`}
                >
                  <LayoutGrid
                    className={`h-5 w-5 mt-0.5 ${
                      preferences.defaultProjectView === "grid"
                        ? "text-[#0EA5E9]"
                        : "text-[#58708F]"
                    }`}
                  />
                  <div>
                    <span className="font-semibold text-sm text-[#0F2747] block">
                      Grid View (Cards)
                    </span>
                    <span className="text-xs text-[#58708F]">
                      Rich card display with progress bars and status indicators.
                    </span>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => updateField("defaultProjectView", "table")}
                  className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all ${
                    preferences.defaultProjectView === "table"
                      ? "border-[#0EA5E9] bg-sky-50/50 ring-1 ring-[#0EA5E9]"
                      : "border-[#DCE6F0] bg-white hover:border-slate-300"
                  }`}
                >
                  <List
                    className={`h-5 w-5 mt-0.5 ${
                      preferences.defaultProjectView === "table"
                        ? "text-[#0EA5E9]"
                        : "text-[#58708F]"
                    }`}
                  />
                  <div>
                    <span className="font-semibold text-sm text-[#0F2747] block">
                      Table View (Compact List)
                    </span>
                    <span className="text-xs text-[#58708F]">
                      Dense tabular format for managing large project catalogs.
                    </span>
                  </div>
                </button>
              </div>
            </div>

            {/* Default Cross-Check Filter */}
            <div className="space-y-3 pt-2 border-t border-[#DCE6F0]">
              <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                <GitCompare className="h-3.5 w-3.5 text-[#0EA5E9]" />
                Default CrossCheck Matrix Filter
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => updateField("defaultCrossCheckView", "all")}
                  className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all ${
                    preferences.defaultCrossCheckView === "all"
                      ? "border-[#0EA5E9] bg-sky-50/50 ring-1 ring-[#0EA5E9]"
                      : "border-[#DCE6F0] bg-white hover:border-slate-300"
                  }`}
                >
                  <Sparkles
                    className={`h-5 w-5 mt-0.5 ${
                      preferences.defaultCrossCheckView === "all"
                        ? "text-[#0EA5E9]"
                        : "text-[#58708F]"
                    }`}
                  />
                  <div>
                    <span className="font-semibold text-sm text-[#0F2747] block">
                      Show All Match Groups
                    </span>
                    <span className="text-xs text-[#58708F]">
                      View both matching items and discrepancies together.
                    </span>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => updateField("defaultCrossCheckView", "discrepancies_only")}
                  className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all ${
                    preferences.defaultCrossCheckView === "discrepancies_only"
                      ? "border-[#0EA5E9] bg-sky-50/50 ring-1 ring-[#0EA5E9]"
                      : "border-[#DCE6F0] bg-white hover:border-slate-300"
                  }`}
                >
                  <AlertTriangle
                    className={`h-5 w-5 mt-0.5 ${
                      preferences.defaultCrossCheckView === "discrepancies_only"
                        ? "text-[#0EA5E9]"
                        : "text-[#58708F]"
                    }`}
                  />
                  <div>
                    <span className="font-semibold text-sm text-[#0F2747] block">
                      Discrepancies Only
                    </span>
                    <span className="text-xs text-[#58708F]">
                      Focus strictly on items requiring human review or escalation.
                    </span>
                  </div>
                </button>
              </div>
            </div>

            {/* Auto-Refresh & Safety */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2 border-t border-[#DCE6F0]">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                  <RotateCw className="h-3.5 w-3.5 text-[#0EA5E9]" />
                  Processing Status Polling
                </label>
                <select
                  value={preferences.autoRefreshInterval}
                  onChange={(e) => updateField("autoRefreshInterval", Number(e.target.value))}
                  className="w-full h-10 px-3 rounded-lg border border-[#DCE6F0] bg-white text-sm text-[#0F2747] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]"
                >
                  <option value={3}>Fast (Every 3 seconds)</option>
                  <option value={5}>Balanced (Every 5 seconds - Default)</option>
                  <option value={10}>Conservative (Every 10 seconds)</option>
                  <option value={0}>Manual Only (No Auto-Poll)</option>
                </select>
                <p className="text-[11px] text-[#58708F]">
                  Controls how frequently the active processing pipeline polls the backend.
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-[#0EA5E9]" />
                  Safety Dialogs
                </label>
                <div className="flex items-center justify-between p-3 rounded-lg border border-[#DCE6F0] bg-[#F7F9FC]">
                  <div className="space-y-0.5">
                    <span className="text-sm font-medium text-[#0F2747]">
                      Confirm Destructive Actions
                    </span>
                    <p className="text-[11px] text-[#58708F]">
                      Show confirmation modal before deleting documents or reports.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={preferences.confirmDestructiveActions}
                    onChange={(e) => updateField("confirmDestructiveActions", e.target.checked)}
                    className="h-4 w-4 rounded text-[#0EA5E9] focus:ring-[#0EA5E9] border-slate-300"
                  />
                </div>
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex justify-between items-center border-t border-[#DCE6F0] bg-[#FAFCFF] py-3.5">
            <span className="text-xs text-[#58708F]">
              Preferences apply immediately to your browser session.
            </span>
            <Button type="submit" className="min-w-[130px]">
              {isSaved ? (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Saved
                </>
              ) : (
                "Save Preferences"
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

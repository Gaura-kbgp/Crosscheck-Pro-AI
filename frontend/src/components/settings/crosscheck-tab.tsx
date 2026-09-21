"use client";

import React, { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import {
  useCrossCheckConfig,
  CrossCheckWorkspaceConfig,
} from "@/lib/hooks/use-crosscheck-preferences";
import {
  GitCompare,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  Check,
  Layers,
  Sparkles,
  Sliders,
  Ruler,
  DollarSign,
  Play,
  RotateCcw,
  Loader2,
  Zap,
} from "lucide-react";

export function CrossCheckTab() {
  const { config, isLoading, isSaving, saveConfig } = useCrossCheckConfig();
  const [formState, setFormState] = useState<CrossCheckWorkspaceConfig>(config);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sync state when config loads from server
  useEffect(() => {
    setFormState(config);
  }, [config]);

  // Simulator State for interactive real-time verification testing
  const [simDesignWidth, setSimDesignWidth] = useState("36.00");
  const [simAckWidth, setSimAckWidth] = useState("36.15");
  const [simDesignQty, setSimDesignQty] = useState(4);
  const [simAckQty, setSimAckQty] = useState(4);

  const toggleField = (key: keyof CrossCheckWorkspaceConfig) => {
    setFormState((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const updateNumericField = (
    key: keyof CrossCheckWorkspaceConfig,
    value: number
  ) => {
    setFormState((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSaveSuccess(false);

    try {
      await saveConfig(formState);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to save CrossCheck preferences"
      );
    }
  };

  // Live Simulator Evaluation
  const designWidthNum = parseFloat(simDesignWidth) || 0;
  const ackWidthNum = parseFloat(simAckWidth) || 0;
  const widthDelta = Math.abs(designWidthNum - ackWidthNum);
  const isWidthOutOfTolerance = widthDelta > formState.dimensionToleranceInches;
  const isQtyMismatch = simDesignQty !== simAckQty;

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-[#0EA5E9]">
                <GitCompare className="h-5 w-5" />
              </div>
              <div>
                <CardTitle>CrossCheck Preferences & Tolerances</CardTitle>
                <CardDescription>
                  Configure live verification tolerances, review queue automation, and discrepancy sensitivity.
                </CardDescription>
              </div>
            </div>
            <Badge variant="success" dot dotColor="bg-emerald-500">
              Live Connected
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="p-4 bg-sky-50/50 border border-sky-100 rounded-xl flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-[#0EA5E9] shrink-0 mt-0.5" />
            <div className="text-xs text-sky-950 space-y-1">
              <p className="font-semibold">
                Real-Time Workspace Verification Configuration
              </p>
              <p className="text-sky-800 leading-relaxed">
                Settings saved here are stored directly in your workspace settings and are immediately applied during Three-Way CrossCheck matching and discrepancy reviews.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Preferences Form */}
      <Card>
        <CardHeader>
          <CardTitle>Discrepancy Sensitivity & Tolerances</CardTitle>
          <CardDescription>
            Control variance margins before line items are flagged for human review.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSave}>
          <CardContent className="space-y-6">
            {saveSuccess && (
              <Alert variant="success" title="Preferences Synchronized">
                Your CrossCheck verification rules and review tolerances have been saved to the workspace.
              </Alert>
            )}

            {errorMessage && (
              <Alert variant="destructive" title="Save Error">
                {errorMessage}
              </Alert>
            )}

            {/* Dimensional Tolerance */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                  <Ruler className="h-3.5 w-3.5 text-[#0EA5E9]" />
                  Dimensional Drift Tolerance
                </label>
                <span className="font-mono text-xs font-bold text-[#0EA5E9] bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
                  Current: ±{formState.dimensionToleranceInches}&quot;
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { label: "Strict", value: 0.0, desc: "Exact 0.00\" match. Flags any fractional difference." },
                  { label: "Standard (Recommended)", value: 0.125, desc: "Allows up to ±1/8\" (0.125\") fabrication drift." },
                  { label: "Flexible", value: 0.25, desc: "Allows up to ±1/4\" (0.250\") tolerance variance." },
                ].map((tier) => {
                  const isSelected = formState.dimensionToleranceInches === tier.value;
                  return (
                    <button
                      key={tier.label}
                      type="button"
                      onClick={() => updateNumericField("dimensionToleranceInches", tier.value)}
                      className={`p-3.5 rounded-xl border text-left transition-all ${
                        isSelected
                          ? "border-[#0EA5E9] bg-sky-50/60 ring-1 ring-[#0EA5E9]"
                          : "border-[#DCE6F0] bg-white hover:border-slate-300"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-sm text-[#0F2747]">{tier.label}</span>
                        <span className="font-mono text-xs font-semibold text-[#58708F]">±{tier.value}&quot;</span>
                      </div>
                      <p className="text-xs text-[#58708F]">{tier.desc}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Price Variance Flagging */}
            <div className="space-y-3 pt-4 border-t border-[#DCE6F0]">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                  <DollarSign className="h-3.5 w-3.5 text-[#0EA5E9]" />
                  Unit Price Variance Threshold
                </label>
                <span className="font-mono text-xs font-bold text-[#0EA5E9] bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
                  {formState.priceVariancePercent === 0 ? "Disabled" : `±${formState.priceVariancePercent}%`}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                {[
                  { label: "Strict (±1%)", value: 1 },
                  { label: "Standard (±5%)", value: 5 },
                  { label: "Lenient (±10%)", value: 10 },
                  { label: "Do Not Flag", value: 0 },
                ].map((item) => {
                  const isSelected = formState.priceVariancePercent === item.value;
                  return (
                    <button
                      key={item.label}
                      type="button"
                      onClick={() => updateNumericField("priceVariancePercent", item.value)}
                      className={`p-3 rounded-xl border text-center font-semibold text-sm transition-all ${
                        isSelected
                          ? "border-[#0EA5E9] bg-sky-50/60 text-[#0EA5E9] ring-1 ring-[#0EA5E9]"
                          : "border-[#DCE6F0] bg-white text-[#0F2747] hover:border-slate-300"
                      }`}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Review Queue Automation Switches */}
            <div className="space-y-3 pt-4 border-t border-[#DCE6F0]">
              <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-[#0EA5E9]" />
                Review Queue Automation & Workflow Rules
              </label>

              <div className="divide-y divide-[#DCE6F0] border border-[#DCE6F0] rounded-xl bg-white overflow-hidden">
                <div
                  onClick={() => toggleField("highlightCriticalFirst")}
                  className="flex items-start justify-between p-4 hover:bg-[#F7F9FC]/60 transition-colors cursor-pointer"
                >
                  <div className="space-y-0.5 pr-4">
                    <span className="text-sm font-semibold text-[#0F2747] block">
                      Prioritize Critical Discrepancies
                    </span>
                    <p className="text-xs text-[#58708F]">
                      Sort missing items and quantity mismatches at the top of the CrossCheck review queue.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={formState.highlightCriticalFirst}
                    onChange={() => {}}
                    className="h-4 w-4 rounded text-[#0EA5E9] focus:ring-[#0EA5E9] border-slate-300 pointer-events-none mt-1"
                  />
                </div>

                <div
                  onClick={() => toggleField("autoAdvanceReview")}
                  className="flex items-start justify-between p-4 hover:bg-[#F7F9FC]/60 transition-colors cursor-pointer"
                >
                  <div className="space-y-0.5 pr-4">
                    <span className="text-sm font-semibold text-[#0F2747] block">
                      Auto-Advance Review Queue
                    </span>
                    <p className="text-xs text-[#58708F]">
                      Automatically move to the next unresolved discrepancy after approving, escalating, or overriding an item.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={formState.autoAdvanceReview}
                    onChange={() => {}}
                    className="h-4 w-4 rounded text-[#0EA5E9] focus:ring-[#0EA5E9] border-slate-300 pointer-events-none mt-1"
                  />
                </div>

                <div
                  onClick={() => toggleField("requireReviewNoteOnOverride")}
                  className="flex items-start justify-between p-4 hover:bg-[#F7F9FC]/60 transition-colors cursor-pointer"
                >
                  <div className="space-y-0.5 pr-4">
                    <span className="text-sm font-semibold text-[#0F2747] block">
                      Require Justification Note for Data Overrides
                    </span>
                    <p className="text-xs text-[#58708F]">
                      Enforce audit compliance by requiring a written explanation whenever manually adjusting line item values.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={formState.requireReviewNoteOnOverride}
                    onChange={() => {}}
                    className="h-4 w-4 rounded text-[#0EA5E9] focus:ring-[#0EA5E9] border-slate-300 pointer-events-none mt-1"
                  />
                </div>

                <div
                  onClick={() => toggleField("lockProjectOnFinalize")}
                  className="flex items-start justify-between p-4 hover:bg-[#F7F9FC]/60 transition-colors cursor-pointer"
                >
                  <div className="space-y-0.5 pr-4">
                    <span className="text-sm font-semibold text-[#0F2747] block">
                      Strict Finalization Lock
                    </span>
                    <p className="text-xs text-[#58708F]">
                      Seal the project and lock all discrepancies and exported documents permanently against further modifications.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={formState.lockProjectOnFinalize}
                    onChange={() => {}}
                    className="h-4 w-4 rounded text-[#0EA5E9] focus:ring-[#0EA5E9] border-slate-300 pointer-events-none mt-1"
                  />
                </div>
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex justify-between items-center border-t border-[#DCE6F0] bg-[#FAFCFF] py-3.5">
            <span className="text-xs text-[#58708F]">
              Changes are saved to your workspace and synchronized in real time.
            </span>
            <Button type="submit" disabled={isSaving || isLoading} className="min-w-[130px]">
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : saveSuccess ? (
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

      {/* Interactive Live Rule Simulator */}
      <Card className="border-sky-200 bg-sky-50/20">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-100 text-[#0EA5E9]">
              <Zap className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base">Live Rule Simulator</CardTitle>
              <CardDescription>
                Test how your active tolerance settings evaluate sample document variances in real time.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Dimension Test Input */}
            <div className="p-4 bg-white border border-[#DCE6F0] rounded-xl space-y-3">
              <span className="text-xs font-bold text-[#0F2747] uppercase tracking-wider block">
                1. Test Dimensional Drift
              </span>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="text-[#58708F] block mb-1">Design Spec (Inches)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={simDesignWidth}
                    onChange={(e) => setSimDesignWidth(e.target.value)}
                    className="w-full h-9 px-2.5 rounded-lg border border-[#DCE6F0] bg-slate-50 font-mono text-sm"
                  />
                </div>
                <div>
                  <label className="text-[#58708F] block mb-1">Ack Size (Inches)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={simAckWidth}
                    onChange={(e) => setSimAckWidth(e.target.value)}
                    className="w-full h-9 px-2.5 rounded-lg border border-[#DCE6F0] bg-slate-50 font-mono text-sm"
                  />
                </div>
              </div>

              <div className="p-3 rounded-lg border text-xs flex items-center justify-between mt-2 bg-[#F7F9FC]">
                <span>
                  Delta: <strong>{widthDelta.toFixed(3)}&quot;</strong> (Tolerance: ±{formState.dimensionToleranceInches}&quot;)
                </span>
                {isWidthOutOfTolerance ? (
                  <Badge variant="destructive">
                    Flagged Discrepancy
                  </Badge>
                ) : (
                  <Badge variant="success">
                    In Tolerance
                  </Badge>
                )}
              </div>
            </div>

            {/* Quantity Test Input */}
            <div className="p-4 bg-white border border-[#DCE6F0] rounded-xl space-y-3">
              <span className="text-xs font-bold text-[#0F2747] uppercase tracking-wider block">
                2. Test Quantity Mismatch
              </span>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="text-[#58708F] block mb-1">Design Qty (EA)</label>
                  <input
                    type="number"
                    value={simDesignQty}
                    onChange={(e) => setSimDesignQty(parseInt(e.target.value) || 0)}
                    className="w-full h-9 px-2.5 rounded-lg border border-[#DCE6F0] bg-slate-50 font-mono text-sm"
                  />
                </div>
                <div>
                  <label className="text-[#58708F] block mb-1">Ack Qty (EA)</label>
                  <input
                    type="number"
                    value={simAckQty}
                    onChange={(e) => setSimAckQty(parseInt(e.target.value) || 0)}
                    className="w-full h-9 px-2.5 rounded-lg border border-[#DCE6F0] bg-slate-50 font-mono text-sm"
                  />
                </div>
              </div>

              <div className="p-3 rounded-lg border text-xs flex items-center justify-between mt-2 bg-[#F7F9FC]">
                <span>
                  Variance: <strong>{simDesignQty - simAckQty} EA</strong>
                </span>
                {isQtyMismatch ? (
                  <Badge variant="destructive">
                    Critical Variance
                  </Badge>
                ) : (
                  <Badge variant="success">
                    Quantity Matched
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

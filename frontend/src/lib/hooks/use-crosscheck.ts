import { useQuery } from "@tanstack/react-query";
import { crosscheckApi } from "../api/endpoints";
import { CrossCheckResult, MatchGroup } from "../api/types";

export function useCrossCheck(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "crosscheck"],
    queryFn: async () => {
      if (!projectId) throw new Error("Project ID is required");
      const data = await crosscheckApi.get(projectId);
      
      // Backend returns { match_groups: [...], discrepancies: [...] }
      // Map it to CrossCheckResult
      const rawData = data as any;
      const groups: MatchGroup[] = (rawData.match_groups || []).map((mg: any) => ({
        id: mg.id,
        project_id: mg.project_id,
        canonical_sku: mg.final_sku || "Unknown SKU",
        canonical_item_id: mg.design_item_id || mg.order_item_id || mg.ack_item_id || null,
        status: mg.status,
        final_sku: mg.final_sku,
        final_quantity: mg.final_quantity,
        final_dimensions: typeof mg.final_dimensions === "object" ? JSON.stringify(mg.final_dimensions) : mg.final_dimensions,
        final_finish: mg.final_finish,
        final_door_style: mg.final_door_style,
        final_modifications: typeof mg.final_modifications === "object" ? JSON.stringify(mg.final_modifications) : mg.final_modifications,
        final_unit_price: mg.final_price ? parseFloat(mg.final_price) : null,
        // F8.3 Phase 2: pass through only what Human Review needs for source
        // traceability (raw_sku + the evidence block) — not the full canonical
        // item record.
        design_item: mg.design_item ? { raw_sku: mg.design_item.raw_sku, source_metadata: mg.design_item.source_metadata } : null,
        order_item: mg.order_item ? { raw_sku: mg.order_item.raw_sku, source_metadata: mg.order_item.source_metadata } : null,
        ack_item: mg.ack_item ? { raw_sku: mg.ack_item.raw_sku, source_metadata: mg.ack_item.source_metadata } : null,
        // design_value / order_value / ack_value / field_name / severity / introduced_at
        // are all computed server-side (DiscrepancyResponse + CrossCheckEngine) from the
        // same source_values record, so every consumer of this hook renders identical state —
        // no per-field re-derivation here.
        discrepancies: (mg.discrepancies || []).map((d: any) => {
          const stringify = (v: any) => (typeof v === "object" && v !== null ? JSON.stringify(v) : (v ?? null));
          return {
            id: d.id,
            match_group_id: d.match_group_id,
            field_name: d.field_name ?? d.field,
            design_value: stringify(d.design_value),
            order_value: stringify(d.order_value),
            ack_value: stringify(d.ack_value),
            severity: d.severity,
            introduced_at: d.introduced_at,
            status: d.status,
            explanation: d.explanation,
            created_at: d.created_at,
            updated_at: d.updated_at,
          };
        })
      }));

      // discrepancy_summary is the backend's single source of truth for the Human
      // Review summary cards (see DiscrepancySummary in app/api/v1/crosscheck.py) —
      // computed from the full, unfiltered finding set, so open === critical + high
      // + warning + info always holds and never drifts from what's rendered here.
      const discrepancySummary = rawData.discrepancy_summary || {
        open: 0, escalated: 0, reviewed: 0, critical: 0, high: 0, warning: 0, info: 0,
      };

      const summary = {
        total_groups: groups.length,
        matched: groups.filter(g => g.status === "MATCHED").length,
        changed: groups.filter(g => g.status === "CHANGED").length,
        missing: groups.filter(g => g.status === "MISSING").length,
        extra: groups.filter(g => g.status === "EXTRA").length,
        uncertain: groups.filter(g => g.status === "UNCERTAIN").length,
        critical_discrepancies: discrepancySummary.critical,
        open_reviews: discrepancySummary.open + discrepancySummary.escalated,
      };

      const result: CrossCheckResult = {
        project_id: projectId,
        groups,
        discrepancySummary,
        summary
      };

      return result;
    },
    enabled: !!projectId,
  });
}

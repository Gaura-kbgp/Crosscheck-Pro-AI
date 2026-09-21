import { useQuery } from "@tanstack/react-query";
import { crosscheckApi } from "../api/endpoints";
import { CrossCheckResult, MatchGroup, Discrepancy } from "../api/types";

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
        discrepancies: (mg.discrepancies || []).map((d: any) => {
          let designVal = null;
          let orderVal = null;
          let ackVal = null;

          if (typeof d.source_values === "object" && d.source_values !== null) {
            designVal = d.source_values.design || d.source_values.DESIGN || null;
            orderVal = d.source_values.order || d.source_values.ORDER || null;
            ackVal = d.source_values.ack || d.source_values.ACKNOWLEDGEMENT || null;
          } else if (typeof d.source_values === "string") {
            designVal = d.source_values;
          }

          if (typeof d.comparison_values === "object" && d.comparison_values !== null) {
            if (!orderVal) orderVal = d.comparison_values.order || d.comparison_values.ORDER || null;
            if (!ackVal) ackVal = d.comparison_values.ack || d.comparison_values.ACKNOWLEDGEMENT || null;
            if (!designVal) designVal = d.comparison_values.design || d.comparison_values.DESIGN || null;
          } else if (typeof d.comparison_values === "string") {
            orderVal = orderVal || d.comparison_values;
          }

          return {
            id: d.id,
            match_group_id: d.match_group_id,
            field_name: d.field,
            design_value: typeof designVal === "object" && designVal !== null ? JSON.stringify(designVal) : (designVal ?? null),
            order_value: typeof orderVal === "object" && orderVal !== null ? JSON.stringify(orderVal) : (orderVal ?? null),
            ack_value: typeof ackVal === "object" && ackVal !== null ? JSON.stringify(ackVal) : (ackVal ?? null),
            severity: d.severity,
            introduced_at: d.introduced_at,
            status: d.status,
            explanation: d.explanation,
            created_at: d.created_at,
            updated_at: d.updated_at,
          };
        })
      }));

      const summary = {
        total_groups: groups.length,
        matched: groups.filter(g => g.status === "MATCHED").length,
        changed: groups.filter(g => g.status === "CHANGED").length,
        missing: groups.filter(g => g.status === "MISSING").length,
        extra: groups.filter(g => g.status === "EXTRA").length,
        uncertain: groups.filter(g => g.status === "UNCERTAIN").length,
        critical_discrepancies: groups.flatMap(g => g.discrepancies).filter(d => d.severity === "CRITICAL").length,
        open_reviews: groups.flatMap(g => g.discrepancies).filter(d => d.status === "OPEN" || d.status === "ESCALATED").length,
      };

      const result: CrossCheckResult = {
        project_id: projectId,
        groups,
        summary
      };
      
      return result;
    },
    enabled: !!projectId,
  });
}

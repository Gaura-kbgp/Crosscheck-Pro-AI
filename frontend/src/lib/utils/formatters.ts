/**
 * Cleanly formats raw JSON strings, dimension dictionaries, and discrepancy values for human display.
 */
export function formatDisplayValue(val: any): string {
  if (val === null || val === undefined || val === "" || val === "null" || val === "None" || val === "undefined") {
    return "—";
  }

  // If it's a string, try parsing as JSON if it starts with { or [
  let parsed = val;
  if (typeof val === "string") {
    const trimmed = val.trim();
    if (trimmed === "null" || trimmed === "None" || trimmed === "" || trimmed === "undefined") {
      return "—";
    }
    if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
      try {
        parsed = JSON.parse(trimmed);
      } catch {
        try {
          parsed = JSON.parse(trimmed.replace(/'/g, '"'));
        } catch {
          parsed = trimmed;
        }
      }
    } else {
      return trimmed;
    }
  }

  // Handle Array
  if (Array.isArray(parsed)) {
    if (parsed.length === 0) return "—";
    return parsed.map((item) => formatDisplayValue(item)).join(", ");
  }

  // Handle Object (Dimensions, modifications, etc.)
  if (typeof parsed === "object" && parsed !== null) {
    // Check for standard dimension keys
    const width = parsed.width ?? parsed.w ?? parsed.Width ?? parsed.W;
    const height = parsed.height ?? parsed.h ?? parsed.Height ?? parsed.H;
    const depth = parsed.depth ?? parsed.d ?? parsed.Depth ?? parsed.D;
    const opening = parsed.opening ?? parsed.Opening;

    if (opening) {
      return String(opening);
    }

    if (
      (width !== undefined && width !== null && width !== "") ||
      (height !== undefined && height !== null && height !== "") ||
      (depth !== undefined && depth !== null && depth !== "")
    ) {
      const formatDimPart = (dim: any, label: string) => {
        if (dim === null || dim === undefined || dim === "" || dim === "null") return null;
        const str = String(dim).replace(/\\/g, "").trim();
        if (str.toLowerCase().endsWith("w") || str.toLowerCase().endsWith("h") || str.toLowerCase().endsWith("d") || str.includes('"')) {
          return str;
        }
        return `${str}"${label}`;
      };

      const wStr = formatDimPart(width, "W");
      const hStr = formatDimPart(height, "H");
      const dStr = formatDimPart(depth, "D");

      const dims = [wStr, hStr, dStr].filter(Boolean);
      if (dims.length > 0) {
        return dims.join(" × ");
      }
    }

    // Generic object key-value formatter
    const parts: string[] = [];
    for (const [k, v] of Object.entries(parsed)) {
      if (k === "axis_certainty" || k === "unit" || k === "raw") continue;
      if (v !== null && v !== undefined && v !== "null" && v !== "") {
        const cleanVal = typeof v === "object" ? formatDisplayValue(v) : String(v).replace(/\\/g, "").trim();
        if (cleanVal && cleanVal !== "—") {
          parts.push(`${k}: ${cleanVal}`);
        }
      }
    }

    if (parts.length > 0) {
      return parts.join(", ");
    }
    return "—";
  }

  return String(parsed).replace(/\\/g, "").trim();
}

export function formatDimensionBadge(dim: any): string {
  const formatted = formatDisplayValue(dim);
  return formatted === "—" ? "" : formatted;
}


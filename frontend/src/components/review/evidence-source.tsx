import React, { useState } from "react";
import { FileSearch, Loader2 } from "lucide-react";
import { documentsApi } from "@/lib/api/endpoints";
import { SourceEvidence } from "@/lib/api/types";
import { toast } from "sonner";

interface EvidenceSourceProps {
  projectId: string;
  documentId?: string | null;
  evidence?: SourceEvidence | null;
}

/**
 * Shows the exact source text a value was extracted from, plus a one-click
 * "View Source" link that opens the original PDF at the exact page — no new
 * PDF-rendering infra, just the browser's own viewer jumped via #page=N.
 */
export function EvidenceSource({ projectId, documentId, evidence }: EvidenceSourceProps) {
  const [isLoading, setIsLoading] = useState(false);

  if (!evidence?.source_text && !evidence?.page_number) {
    return null;
  }

  const handleViewSource = () => {
    if (!documentId || !evidence?.page_number) return;
    // Open the tab synchronously, inside the click handler, so it carries
    // the user-gesture flag — opening it only after the await below (once
    // the signed URL comes back) loses that flag and gets silently
    // popup-blocked in most browsers. Navigate the already-open tab once
    // the URL resolves instead.
    const win = window.open("", "_blank");
    setIsLoading(true);
    documentsApi.getUrl(projectId, documentId)
      .then((res) => {
        if (res?.url && win) {
          win.location.href = `${res.url}#page=${evidence.page_number}`;
        } else {
          win?.close();
          toast.error("Could not open the source document.");
        }
      })
      .catch(() => {
        win?.close();
        toast.error("Could not open the source document.");
      })
      .finally(() => setIsLoading(false));
  };

  return (
    <div className="mt-1 flex items-start gap-1.5">
      {evidence.source_text && (
        <p className="text-[11px] italic text-[#58708F] line-clamp-2">
          “{evidence.source_text}”
        </p>
      )}
      {documentId && evidence.page_number != null && (
        <button
          type="button"
          onClick={handleViewSource}
          disabled={isLoading}
          title={`View source — page ${evidence.page_number}`}
          className="shrink-0 inline-flex items-center gap-1 text-[11px] font-semibold text-[#0B8FD3] hover:text-[#0EA5E9] disabled:opacity-50"
        >
          {isLoading ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <FileSearch className="h-3 w-3" />
          )}
          Page {evidence.page_number}
        </button>
      )}
    </div>
  );
}

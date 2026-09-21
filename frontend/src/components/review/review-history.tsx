import React from "react";
import { useAuditLogs } from "@/lib/hooks/use-reviews";
import { AuditLog } from "@/lib/api/types";
import { Clock, User } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/utils";

interface ReviewHistoryProps {
  projectId: string;
  resourceId: string;
  title?: string;
}

export function ReviewHistory({ projectId, resourceId, title = "Review History" }: ReviewHistoryProps) {
  const { data: logs, isLoading } = useAuditLogs(projectId);

  if (isLoading) {
    return (
      <div className="space-y-3 p-4 bg-white rounded-xl border border-[#DCE6F0] shadow-2xs">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  const resourceLogs = logs?.filter((log: AuditLog) => log.resource_id === resourceId) || [];

  if (resourceLogs.length === 0) {
    return null; // Don't show anything if no history
  }

  return (
    <div className="bg-white rounded-xl border border-[#DCE6F0] shadow-2xs p-5">
      <h3 className="text-sm font-bold text-[#0F2747] uppercase tracking-wider mb-4 flex items-center gap-2">
        <Clock className="h-4 w-4 text-[#58708F]" />
        {title}
      </h3>
      
      <div className="space-y-4 relative before:absolute before:inset-0 before:ml-2 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-200 before:to-transparent">
        {resourceLogs.map((log) => (
          <div key={log.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
            {/* Icon */}
            <div className="flex items-center justify-center w-5 h-5 rounded-full border border-white bg-slate-200 text-slate-500 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
              <div className="w-1.5 h-1.5 bg-slate-400 rounded-full"></div>
            </div>
            
            {/* Card */}
            <div className="w-[calc(100%-2rem)] md:w-[calc(50%-1.5rem)] p-3 rounded-lg border border-slate-100 bg-slate-50 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <div className="text-xs font-bold text-[#0F2747]">{log.action.replace(/_/g, " ")}</div>
                <div className="text-[10px] font-medium text-[#58708F]">{formatDate(log.created_at)}</div>
              </div>
              
              <div className="text-xs text-[#58708F] flex items-center gap-1 mb-2">
                <User className="h-3 w-3" /> System / Reviewer
              </div>

              {Boolean(log.metadata?.reason) && (
                <div className="text-xs mt-2 bg-white p-2 rounded border border-slate-100 text-[#0F2747] italic">
                  <span className="font-semibold not-italic text-[#58708F]">Reason: </span>
                  {String(log.metadata?.reason)}
                </div>
              )}

              {log.previous_state && log.new_state && Object.keys(log.new_state).length > 0 && (
                <div className="mt-2 text-[11px] bg-slate-100 p-2 rounded">
                  {Object.keys(log.new_state).map(key => (
                    <div key={key} className="flex gap-2 font-mono">
                      <span className="text-[#58708F]">{key}:</span>
                      <span className="line-through text-rose-500">{JSON.stringify(log.previous_state?.[key])}</span>
                      <span className="text-emerald-600">→</span>
                      <span className="text-emerald-600">{JSON.stringify(log.new_state?.[key])}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

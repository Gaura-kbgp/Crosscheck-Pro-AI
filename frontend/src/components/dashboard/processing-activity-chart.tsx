"use client";

import React from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ActivityDataPoint } from "@/lib/hooks/use-dashboard";
import { BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";

const SKELETON_HEIGHTS = [35, 65, 45, 80, 55, 70, 40, 60, 50, 75, 45, 65, 40, 85, 55];

interface ProcessingActivityChartProps {
  data: ActivityDataPoint[];
  hasActivity: boolean;
  timeframe: 7 | 30;
  onTimeframeChange: (timeframe: 7 | 30) => void;
  isLoading: boolean;
}

export function ProcessingActivityChart({
  data,
  hasActivity,
  timeframe,
  onTimeframeChange,
  isLoading,
}: ProcessingActivityChartProps) {
  const maxCount = Math.max(...data.map((d) => d.count), 4);

  return (
    <Card className="border border-[#DCE6F0] bg-white">
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 gap-3">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-[#0EA5E9]" />
            Processing Activity
          </CardTitle>
          <CardDescription>
            Project verification and document processing events
          </CardDescription>
        </div>

        {/* Timeframe Filter */}
        <div className="flex items-center rounded-lg border border-[#DCE6F0] bg-[#F7F9FC] p-1 text-xs">
          <button
            type="button"
            onClick={() => onTimeframeChange(7)}
            className={cn(
              "rounded-md px-2.5 py-1 font-medium transition-colors cursor-pointer",
              timeframe === 7
                ? "bg-white text-[#0F2747] shadow-2xs font-semibold"
                : "text-[#58708F] hover:text-[#0F2747]"
            )}
          >
            Last 7 days
          </button>
          <button
            type="button"
            onClick={() => onTimeframeChange(30)}
            className={cn(
              "rounded-md px-2.5 py-1 font-medium transition-colors cursor-pointer",
              timeframe === 30
                ? "bg-white text-[#0F2747] shadow-2xs font-semibold"
                : "text-[#58708F] hover:text-[#0F2747]"
            )}
          >
            Last 30 days
          </button>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div className="h-48 w-full flex items-end gap-2 pt-6">
            {Array.from({ length: timeframe === 7 ? 7 : 15 }).map((_, i) => (
              <Skeleton
                key={i}
                className="w-full rounded-t-md"
                style={{ height: `${SKELETON_HEIGHTS[i % SKELETON_HEIGHTS.length]}%` }}
              />
            ))}
          </div>
        ) : !hasActivity ? (
          <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-[#DCE6F0] bg-[#F7F9FC]/50 p-6 text-center">
            <BarChart3 className="h-8 w-8 text-[#58708F]/50 mb-2" />
            <p className="text-sm font-medium text-[#0F2747]">
              No processing activity yet
            </p>
            <p className="text-xs text-[#58708F] mt-0.5">
              Activity will automatically register as you upload documents and run cross-checks.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="h-48 w-full flex items-end gap-1.5 sm:gap-2 pt-6 pb-2 border-b border-[#DCE6F0]">
              {data.map((item) => {
                const heightPercent =
                  item.count > 0
                    ? Math.max(15, Math.round((item.count / maxCount) * 100))
                    : 4;

                return (
                  <div
                    key={item.date}
                    className="group relative flex flex-1 flex-col items-center h-full justify-end"
                  >
                    {/* Tooltip */}
                    <div className="absolute -top-7 hidden group-hover:flex items-center rounded-md bg-[#0F2747] px-2 py-0.5 text-[10px] font-medium text-white shadow-md z-10 whitespace-nowrap">
                      {item.formattedDate}: {item.count} {item.count === 1 ? "project" : "projects"}
                    </div>

                    {/* Bar */}
                    <div
                      style={{ height: `${heightPercent}%` }}
                      className={cn(
                        "w-full rounded-t-md transition-all duration-300",
                        item.count > 0
                          ? "bg-[#0EA5E9] hover:bg-[#0284C7] group-hover:scale-y-105"
                          : "bg-[#E0F2FE]/60"
                      )}
                    />
                  </div>
                );
              })}
            </div>

            {/* X-axis date labels */}
            <div className="flex justify-between text-[11px] text-[#58708F] font-medium pt-1">
              <span>{data[0]?.formattedDate}</span>
              {data.length > 2 && (
                <span>
                  {data[Math.floor(data.length / 2)]?.formattedDate}
                </span>
              )}
              <span>{data[data.length - 1]?.formattedDate}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

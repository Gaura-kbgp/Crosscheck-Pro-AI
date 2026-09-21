import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DashboardMetrics } from "@/lib/hooks/use-dashboard";
import {
  FolderKanban,
  Loader2,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface KpiCardsProps {
  metrics: DashboardMetrics;
  isLoading: boolean;
}

export function KpiCards({ metrics, isLoading }: KpiCardsProps) {
  const cards = [
    {
      title: "Total Projects",
      value: metrics.totalProjects,
      description: "Active tenant workspace",
      icon: FolderKanban,
      iconColor: "text-[#0EA5E9]",
      iconBg: "bg-[#E0F2FE]",
      borderColor: "border-[#DCE6F0]",
    },
    {
      title: "Processing",
      value: metrics.processingCount,
      description: "Extraction & matching in flight",
      icon: Loader2,
      iconColor: "text-[#7C3AED]",
      iconBg: "bg-[#F3E8FF]",
      borderColor: "border-[#DCE6F0]",
      spinIcon: metrics.processingCount > 0,
    },
    {
      title: "Needs Review",
      value: metrics.needsReviewCount,
      description: "Discrepancies awaiting audit",
      icon: AlertTriangle,
      iconColor: "text-[#F59E0B]",
      iconBg: "bg-[#FEF3C7]",
      borderColor: "border-[#DCE6F0]",
    },
    {
      title: "Completed",
      value: metrics.completedCount,
      description: "Verified & finalized files",
      icon: CheckCircle2,
      iconColor: "text-[#16A34A]",
      iconBg: "bg-[#DCFCE7]",
      borderColor: "border-[#DCE6F0]",
    },
  ];

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="border border-[#DCE6F0] bg-white">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-9 w-9 rounded-lg" />
              </div>
              <Skeleton className="h-8 w-16 mt-3" />
              <Skeleton className="h-3 w-32 mt-2" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <Card
            key={card.title}
            className={cn(
              "border bg-white transition-all duration-200 hover:shadow-2xs",
              card.borderColor
            )}
          >
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                  {card.title}
                </span>
                <div
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-lg shadow-2xs",
                    card.iconBg,
                    card.iconColor
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4.5 w-4.5",
                      card.spinIcon && "animate-spin"
                    )}
                  />
                </div>
              </div>
              <div className="mt-2.5 flex items-baseline gap-2">
                <span className="text-[30px] sm:text-3xl font-bold tracking-tight text-[#0F2747] leading-none">
                  {card.value}
                </span>
              </div>
              <p className="mt-1.5 text-xs text-[#58708F] font-normal leading-normal">{card.description}</p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

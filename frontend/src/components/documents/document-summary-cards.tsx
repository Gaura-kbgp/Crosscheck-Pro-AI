"use client";

import React from "react";
import { Document } from "@/lib/api/types";
import { FileText, Compass, ShoppingCart, CheckCircle2, Loader2 } from "lucide-react";

interface DocumentSummaryCardsProps {
  documents: Document[];
  isLoading?: boolean;
}

export function DocumentSummaryCards({
  documents,
  isLoading = false,
}: DocumentSummaryCardsProps) {
  const totalCount = documents.length;
  const designCount = documents.filter((d) => d.document_type === "DESIGN").length;
  const orderCount = documents.filter((d) => d.document_type === "ORDER").length;
  const ackCount = documents.filter((d) => d.document_type === "ACKNOWLEDGEMENT").length;
  const processingCount = documents.filter(
    (d) => d.status === "PROCESSING" || d.status === "UPLOADED"
  ).length;

  const cards = [
    {
      label: "Total Documents",
      count: totalCount,
      icon: FileText,
      iconBg: "bg-[#F1F5F9]",
      iconColor: "text-[#0F2747]",
    },
    {
      label: "Design",
      count: designCount,
      icon: Compass,
      iconBg: "bg-[#E0F2FE]",
      iconColor: "text-[#0284C7]",
    },
    {
      label: "Purchase Orders",
      count: orderCount,
      icon: ShoppingCart,
      iconBg: "bg-[#FEF3C7]",
      iconColor: "text-[#D97706]",
    },
    {
      label: "Acknowledgements",
      count: ackCount,
      icon: CheckCircle2,
      iconBg: "bg-[#DCFCE7]",
      iconColor: "text-[#16A34A]",
    },
    {
      label: "Processing",
      count: processingCount,
      icon: Loader2,
      iconBg: "bg-[#F3E8FF]",
      iconColor: "text-[#7E22CE]",
      isSpinning: processingCount > 0,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className="flex items-center gap-3 rounded-xl border border-[#DCE6F0] bg-white p-3.5 shadow-2xs transition-all hover:border-[#0EA5E9]/30"
          >
            <div
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${card.iconBg} ${card.iconColor}`}
            >
              <Icon
                className={`h-4.5 w-4.5 ${
                  card.isSpinning ? "animate-spin" : ""
                }`}
              />
            </div>
            <div className="min-w-0">
              <span className="block text-[11px] font-medium text-[#58708F] truncate">
                {card.label}
              </span>
              <span className="text-base font-bold text-[#0F2747] leading-tight">
                {isLoading ? "..." : card.count}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

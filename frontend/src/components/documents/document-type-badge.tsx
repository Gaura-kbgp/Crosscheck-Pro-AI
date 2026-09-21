"use client";

import React from "react";
import { DocumentType } from "@/lib/api/types";
import { Compass, ShoppingCart, CheckCircle2, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

interface DocumentTypeBadgeProps {
  type: DocumentType;
  className?: string;
  showIcon?: boolean;
}

export const DOCUMENT_TYPE_META: Record<
  DocumentType,
  {
    label: string;
    shortLabel: string;
    icon: React.ComponentType<{ className?: string }>;
    badgeStyle: string;
    iconColor: string;
  }
> = {
  DESIGN: {
    label: "Design Document",
    shortLabel: "Design",
    icon: Compass,
    badgeStyle: "bg-[#E0F2FE] text-[#0284C7] border-[#BAE6FD]",
    iconColor: "text-[#0284C7]",
  },
  ORDER: {
    label: "Purchase Order",
    shortLabel: "Purchase Order",
    icon: ShoppingCart,
    badgeStyle: "bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]",
    iconColor: "text-[#D97706]",
  },
  ACKNOWLEDGEMENT: {
    label: "Manufacturer Acknowledgement",
    shortLabel: "Acknowledgement",
    icon: CheckCircle2,
    badgeStyle: "bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]",
    iconColor: "text-[#16A34A]",
  },
};

export function DocumentTypeBadge({
  type,
  className,
  showIcon = true,
}: DocumentTypeBadgeProps) {
  const meta = DOCUMENT_TYPE_META[type] || {
    label: type,
    shortLabel: type,
    icon: FileText,
    badgeStyle: "bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]",
    iconColor: "text-[#58708F]",
  };

  const Icon = meta.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold border select-none transition-colors",
        meta.badgeStyle,
        className
      )}
    >
      {showIcon && <Icon className={cn("h-3.5 w-3.5 shrink-0", meta.iconColor)} />}
      <span>{meta.shortLabel}</span>
    </span>
  );
}

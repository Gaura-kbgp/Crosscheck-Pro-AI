import React from "react";
import { Button } from "@/components/ui/button";
import { LucideIcon, FolderSearch } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
  children?: React.ReactNode;
}

export function EmptyState({
  icon: Icon = FolderSearch,
  title,
  description,
  actionLabel,
  onAction,
  className,
  children,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-[#DCE6F0] bg-white px-6 py-14 text-center",
        className
      )}
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#E0F2FE] text-[#0EA5E9] mb-4">
        <Icon className="h-7 w-7" />
      </div>
      <h3 className="text-base font-semibold text-[#0F2747]">{title}</h3>
      <p className="mt-1.5 max-w-sm text-sm text-[#58708F]">{description}</p>
      {actionLabel && onAction && (
        <div className="mt-6">
          <Button onClick={onAction}>{actionLabel}</Button>
        </div>
      )}
      {children && <div className="mt-6">{children}</div>}
    </div>
  );
}

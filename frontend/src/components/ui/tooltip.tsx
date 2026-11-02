"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

/**
 * Dependency-free hover/focus tooltip. Shown on mouse hover (cursor over)
 * and on keyboard focus (tab onto the trigger) so it's reachable without a
 * mouse, not just a styled `title` attribute.
 */
export function Tooltip({ content, children, className }: TooltipProps) {
  if (!content) return <>{children}</>;

  return (
    <span className={cn("group/tooltip relative inline-flex", className)}>
      <span tabIndex={0} className="outline-none">
        {children}
      </span>
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-max max-w-xs -translate-x-1/2",
          "rounded-lg bg-[#0F2747] px-3 py-2 text-xs font-medium text-white shadow-lg",
          "opacity-0 scale-95 transition-all duration-150",
          "group-hover/tooltip:opacity-100 group-hover/tooltip:scale-100",
          "group-focus-within/tooltip:opacity-100 group-focus-within/tooltip:scale-100"
        )}
      >
        {content}
        <span className="absolute left-1/2 top-full -mt-1 h-2 w-2 -translate-x-1/2 rotate-45 bg-[#0F2747]" />
      </span>
    </span>
  );
}

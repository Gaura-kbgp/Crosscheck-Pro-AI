import React from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  badge?: React.ReactNode;
}

export function PageHeader({
  title,
  description,
  actions,
  badge,
}: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-8">
      <div className="space-y-1.5">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl sm:text-[28px] lg:text-[30px] font-bold tracking-tight text-[#0F2747] leading-tight">
            {title}
          </h1>
          {badge}
        </div>
        {description && (
          <p className="text-sm sm:text-[15px] text-[#58708F] max-w-2xl font-normal leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2.5 shrink-0">{actions}</div>}
    </div>
  );
}

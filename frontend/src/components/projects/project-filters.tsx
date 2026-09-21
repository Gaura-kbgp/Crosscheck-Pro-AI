"use client";

import React from "react";
import { Search, X, ArrowUpDown, Filter, LayoutGrid, List } from "lucide-react";
import { ProjectStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export type StatusFilterOption = "ALL" | ProjectStatus;
export type SortOption = "updated_desc" | "updated_asc" | "name_asc" | "name_desc";
export type ViewMode = "cards" | "table";

interface ProjectFiltersProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  statusFilter: StatusFilterOption;
  onStatusChange: (status: StatusFilterOption) => void;
  sortBy: SortOption;
  onSortChange: (sort: SortOption) => void;
  statusCounts: Record<StatusFilterOption, number>;
  viewMode?: ViewMode;
  onViewModeChange?: (mode: ViewMode) => void;
}

const statusOptions: { label: string; value: StatusFilterOption }[] = [
  { label: "All", value: "ALL" },
  { label: "Draft", value: "DRAFT" },
  { label: "Processing", value: "PROCESSING" },
  { label: "Needs Review", value: "REVIEW_REQUIRED" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Finalized", value: "FINALIZED" },
  { label: "Failed", value: "FAILED" },
];

export function ProjectFilters({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusChange,
  sortBy,
  onSortChange,
  statusCounts,
  viewMode = "cards",
  onViewModeChange,
}: ProjectFiltersProps) {
  return (
    <div className="space-y-3">
      {/* Top Bar: Search, Sort & View Mode Toggle */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Search Field */}
        <div className="relative flex-1 max-w-md">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-[#58708F]">
            <Search className="h-4 w-4" />
          </div>
          <input
            type="text"
            placeholder="Search projects by name, customer, or dealer..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full rounded-lg border border-[#DCE6F0] bg-white py-2 pl-9 pr-8 text-sm text-[#0F2747] placeholder:text-[#58708F] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors shadow-2xs"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange("")}
              className="absolute inset-y-0 right-0 flex items-center pr-2.5 text-[#58708F] hover:text-[#0F2747]"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Sort & View Mode Controls */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center gap-1.5 rounded-lg border border-[#DCE6F0] bg-white px-2.5 py-1.5 shadow-2xs text-xs font-medium text-[#58708F]">
            <ArrowUpDown className="h-3.5 w-3.5 text-[#58708F] shrink-0" />
            <span className="hidden sm:inline text-[#58708F]">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => onSortChange(e.target.value as SortOption)}
              className="bg-transparent text-[#0F2747] font-semibold focus:outline-none cursor-pointer pr-1"
            >
              <option value="updated_desc">Last Updated</option>
              <option value="updated_asc">Oldest Updated</option>
              <option value="name_asc">Name (A-Z)</option>
              <option value="name_desc">Name (Z-A)</option>
            </select>
          </div>

          {/* View Mode Toggle */}
          {onViewModeChange && (
            <div className="flex items-center rounded-lg border border-[#DCE6F0] bg-white p-0.5 shadow-2xs">
              <button
                type="button"
                onClick={() => onViewModeChange("cards")}
                title="Card Grid View"
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-md text-xs transition-colors",
                  viewMode === "cards"
                    ? "bg-[#0EA5E9] text-white font-semibold"
                    : "text-[#58708F] hover:bg-[#F7F9FC] hover:text-[#0F2747]"
                )}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onViewModeChange("table")}
                title="Table View"
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-md text-xs transition-colors",
                  viewMode === "table"
                    ? "bg-[#0EA5E9] text-white font-semibold"
                    : "text-[#58708F] hover:bg-[#F7F9FC] hover:text-[#0F2747]"
                )}
              >
                <List className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Status Filter Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none pt-0.5">
        <div className="flex items-center text-xs font-semibold text-[#58708F] mr-1 shrink-0">
          <Filter className="h-3 w-3 mr-1 text-[#58708F]" />
          Status:
        </div>
        {statusOptions.map((option) => {
          const count = statusCounts[option.value] ?? 0;
          const isActive = statusFilter === option.value;

          return (
            <button
              key={option.value}
              onClick={() => onStatusChange(option.value)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all shrink-0 cursor-pointer",
                isActive
                  ? "bg-[#0EA5E9] text-white shadow-2xs font-semibold"
                  : "bg-white border border-[#DCE6F0] text-[#58708F] hover:bg-[#F7F9FC] hover:text-[#0F2747]"
              )}
            >
              <span>{option.label}</span>
              <span
                className={cn(
                  "rounded-full px-1.5 py-0.2 text-[10px] font-semibold",
                  isActive
                    ? "bg-white/25 text-white"
                    : "bg-[#F1F5F9] text-[#475569]"
                )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}


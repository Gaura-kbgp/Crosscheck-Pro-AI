"use client";

import React from "react";
import { Project, DocumentType } from "@/lib/api/types";
import { Search, Folder, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export type TypeFilterOption = "ALL" | DocumentType;
export type StatusFilterOption = "ALL" | "PROCESSING" | "READY" | "FAILED";

interface DocumentFilterBarProps {
  projects: Project[];
  selectedProjectId: string;
  onProjectChange: (projectId: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  typeFilter: TypeFilterOption;
  onTypeFilterChange: (type: TypeFilterOption) => void;
  statusFilter: StatusFilterOption;
  onStatusFilterChange: (status: StatusFilterOption) => void;
  onResetFilters?: () => void;
  totalResultsCount?: number;
}

export function DocumentFilterBar({
  projects,
  selectedProjectId,
  onProjectChange,
  searchQuery,
  onSearchChange,
  typeFilter,
  onTypeFilterChange,
  statusFilter,
  onStatusFilterChange,
  onResetFilters,
  totalResultsCount,
}: DocumentFilterBarProps) {
  const isFiltered = searchQuery !== "" || typeFilter !== "ALL" || statusFilter !== "ALL";

  return (
    <div className="space-y-3.5 rounded-xl border border-[#DCE6F0] bg-white p-4 shadow-2xs">
      {/* Top Row: Project Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#DCE6F0]">
        <div className="flex flex-col sm:flex-row sm:items-center gap-2.5 w-full sm:w-auto">
          <label className="text-xs font-bold text-[#0F2747] flex items-center gap-1.5 shrink-0">
            <Folder className="h-4 w-4 text-[#0EA5E9]" />
            Project:
          </label>
          <div className="relative min-w-[240px] sm:min-w-[280px]">
            <select
              value={selectedProjectId}
              onChange={(e) => onProjectChange(e.target.value)}
              className="w-full appearance-none rounded-lg border border-[#DCE6F0] bg-[#F7F9FC] px-3.5 py-2 pr-8 text-xs font-bold text-[#0F2747] shadow-2xs focus:border-[#0EA5E9] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
            >
              <option value="">-- Select a project --</option>
              {projects.map((proj) => (
                <option key={proj.id} value={proj.id}>
                  {proj.name}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#58708F] text-xs">
              ▾
            </div>
          </div>
        </div>

        {totalResultsCount !== undefined && selectedProjectId && (
          <span className="text-xs font-medium text-[#58708F]">
            Showing <strong className="text-[#0F2747]">{totalResultsCount}</strong> documents
          </span>
        )}
      </div>

      {/* Bottom Row: Search, Type & Status Filters */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#58708F]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search documents by filename..."
            className="w-full rounded-lg border border-[#DCE6F0] bg-white pl-9 pr-3 py-1.5 text-xs font-medium text-[#0F2747] placeholder-[#58708F]/70 focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
          />
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Document Type Dropdown */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-semibold text-[#58708F] hidden sm:inline">
              Type:
            </span>
            <select
              value={typeFilter}
              onChange={(e) => onTypeFilterChange(e.target.value as TypeFilterOption)}
              className="rounded-lg border border-[#DCE6F0] bg-white px-2.5 py-1.5 text-xs font-medium text-[#0F2747] focus:border-[#0EA5E9] focus:outline-none"
            >
              <option value="ALL">All Types</option>
              <option value="DESIGN">Design</option>
              <option value="ORDER">Purchase Order</option>
              <option value="ACKNOWLEDGEMENT">Acknowledgement</option>
            </select>
          </div>

          {/* Status Dropdown */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-semibold text-[#58708F] hidden sm:inline">
              Status:
            </span>
            <select
              value={statusFilter}
              onChange={(e) => onStatusFilterChange(e.target.value as StatusFilterOption)}
              className="rounded-lg border border-[#DCE6F0] bg-white px-2.5 py-1.5 text-xs font-medium text-[#0F2747] focus:border-[#0EA5E9] focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="READY">Ready</option>
              <option value="PROCESSING">Processing</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>

          {/* Reset Filters */}
          {isFiltered && onResetFilters && (
            <Button
              variant="outline"
              size="sm"
              onClick={onResetFilters}
              leftIcon={<RefreshCw className="h-3 w-3" />}
              className="h-8 px-2.5 text-[11px] text-[#58708F]"
            >
              Reset
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

import React from "react";
import { Search } from "lucide-react";

interface ReviewFiltersProps {
  statusFilter: string;
  onStatusChange: (v: string) => void;
  severityFilter: string;
  onSeverityChange: (v: string) => void;
  searchQuery: string;
  onSearchChange: (v: string) => void;
}

export function ReviewFilters({
  statusFilter,
  onStatusChange,
  severityFilter,
  onSeverityChange,
  searchQuery,
  onSearchChange,
}: ReviewFiltersProps) {
  return (
    <div className="bg-[#F7F9FC] border-b border-[#DCE6F0] p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
      <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
        {/* Status Filter */}
        <div className="flex items-center gap-2">
          <label className="text-xs font-bold text-[#58708F] uppercase tracking-wider">Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => onStatusChange(e.target.value)}
            className="text-sm border border-[#DCE6F0] rounded-md px-2 py-1.5 bg-white text-[#0F2747] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]"
          >
            <option value="All">All</option>
            <option value="OPEN">Open</option>
            <option value="ESCALATED">Escalated</option>
            <option value="ACCEPTED">Accepted</option>
            <option value="FALSE_POSITIVE">False Positive</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
          </select>
        </div>

        {/* Severity Filter */}
        <div className="flex items-center gap-2">
          <label className="text-xs font-bold text-[#58708F] uppercase tracking-wider">Severity:</label>
          <select
            value={severityFilter}
            onChange={(e) => onSeverityChange(e.target.value)}
            className="text-sm border border-[#DCE6F0] rounded-md px-2 py-1.5 bg-white text-[#0F2747] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]"
          >
            <option value="All">All</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="WARNING">Warning</option>
            <option value="INFO">Info</option>
          </select>
        </div>
      </div>

      {/* Search */}
      <div className="relative w-full md:w-64">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="h-4 w-4 text-[#58708F]" />
        </div>
        <input
          type="text"
          placeholder="Search items..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full pl-9 pr-3 py-1.5 border border-[#DCE6F0] rounded-md text-sm bg-white text-[#0F2747] placeholder:text-[#58708F]/60 focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]"
        />
      </div>
    </div>
  );
}

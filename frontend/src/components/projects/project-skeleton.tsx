"use client";

import React from "react";
import { Skeleton } from "@/components/ui/skeleton";

export function ProjectsPageSkeleton() {
  return (
    <div className="space-y-6">
      {/* Search & Filter Skeleton */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <Skeleton className="h-10 w-full sm:w-80 rounded-lg" />
        <Skeleton className="h-9 w-36 rounded-lg" />
      </div>

      <div className="flex gap-2">
        <Skeleton className="h-7 w-16 rounded-full" />
        <Skeleton className="h-7 w-20 rounded-full" />
        <Skeleton className="h-7 w-28 rounded-full" />
        <Skeleton className="h-7 w-24 rounded-full" />
      </div>

      {/* Desktop Table Skeleton */}
      <div className="hidden lg:block rounded-xl border border-slate-200 bg-white p-4 space-y-4">
        <div className="flex justify-between border-b border-slate-100 pb-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-8" />
        </div>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between py-3 border-b border-slate-50 last:border-0">
            <div className="space-y-1.5 w-1/3">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-32" />
            </div>
            <Skeleton className="h-6 w-24 rounded-full" />
            <Skeleton className="h-5 w-28 rounded" />
            <Skeleton className="h-2 w-24 rounded-full" />
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-6 w-6 rounded" />
          </div>
        ))}
      </div>

      {/* Mobile Cards Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:hidden">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-28" />
              </div>
              <Skeleton className="h-6 w-6 rounded" />
            </div>
            <div className="flex justify-between">
              <Skeleton className="h-5 w-20 rounded-full" />
              <Skeleton className="h-5 w-24" />
            </div>
            <Skeleton className="h-2 w-full rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

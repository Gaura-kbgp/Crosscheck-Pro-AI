"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/store/auth-store";
import { useDashboard } from "@/lib/hooks/use-dashboard";
import { PageHeader } from "@/components/layout/page-header";
import { KpiCards } from "@/components/dashboard/kpi-cards";
import { ProcessingActivityChart } from "@/components/dashboard/processing-activity-chart";
import { RecentProjectsCard } from "@/components/dashboard/recent-projects-card";
import { ErrorState } from "@/components/feedback/error-state";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function getUserFirstName(email?: string, name?: string): string {
  if (name) {
    const parts = name.trim().split(" ");
    if (parts[0]) return parts[0];
  }
  if (email) {
    const username = email.split("@")[0];
    if (username) {
      // Capitalize first letter of username
      return username.charAt(0).toUpperCase() + username.slice(1);
    }
  }
  return "there";
}

export default function DashboardPage() {
  const { user, profile } = useAuthStore();
  const [timeframe, setTimeframe] = useState<7 | 30>(7);
  const {
    metrics,
    activityData,
    hasActivity,
    isLoading,
    error,
    refetch,
  } = useDashboard(timeframe);

  const greeting = getGreeting();
  const firstName = getUserFirstName(profile?.email || user?.email);

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader
          title={`${greeting}, ${firstName}`}
          description="Here's what's happening with your projects today."
        />
        <ErrorState
          title="Unable to load dashboard metrics"
          message={
            error instanceof Error
              ? error.message
              : "Failed to connect to the backend API. Please verify your connection."
          }
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <PageHeader
        title={`${greeting}, ${firstName}`}
        description="Here's what's happening with your projects today."
        actions={
          <Link href="/projects">
            <Button
              size="default"
              leftIcon={<Plus className="h-4 w-4" />}
            >
              New Project
            </Button>
          </Link>
        }
      />

      {/* KPI Cards */}
      <section aria-label="Key Performance Indicators">
        <KpiCards metrics={metrics} isLoading={isLoading} />
      </section>

      {/* Main Grid: Recent Projects (3 cols) + Activity Chart (2 cols) */}
      <section
        aria-label="Recent activity and projects"
        className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start"
      >
        <div className="lg:col-span-3">
          <RecentProjectsCard
            projects={metrics.recentProjects}
            isLoading={isLoading}
          />
        </div>

        <div className="lg:col-span-2">
          <ProcessingActivityChart
            data={activityData}
            hasActivity={hasActivity}
            timeframe={timeframe}
            onTimeframeChange={setTimeframe}
            isLoading={isLoading}
          />
        </div>
      </section>
    </div>
  );
}

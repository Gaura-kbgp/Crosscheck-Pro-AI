import React from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ProjectStatusBadge } from "@/components/badges/status-badge";
import { Project } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";
import { FolderKanban, ChevronRight, Plus, ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface RecentProjectsCardProps {
  projects: Project[];
  isLoading: boolean;
}

export function RecentProjectsCard({
  projects,
  isLoading,
}: RecentProjectsCardProps) {
  return (
    <Card className="border border-[#DCE6F0] bg-white">
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2">
            <FolderKanban className="h-4 w-4 text-[#0EA5E9]" />
            Recent Projects
          </CardTitle>
          <CardDescription>
            Latest construction project documents and statuses
          </CardDescription>
        </div>
        <Link
          href="/projects"
          className="text-xs font-semibold text-[#0284C7] hover:text-[#0EA5E9] flex items-center gap-1 transition-colors"
        >
          View all
          <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      </CardHeader>

      <CardContent className="p-0">
        {isLoading ? (
          <div className="divide-y divide-[#DCE6F0] p-5 pt-2 space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-3 first:pt-0"
              >
                <div className="space-y-2">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-28" />
                </div>
                <div className="flex items-center gap-4">
                  <Skeleton className="h-6 w-20 rounded-full" />
                  <Skeleton className="h-3 w-20" />
                </div>
              </div>
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#F7F9FC] text-[#58708F] mb-3 border border-[#DCE6F0]">
              <FolderKanban className="h-6 w-6" />
            </div>
            <p className="text-sm font-semibold text-[#0F2747]">
              No projects yet
            </p>
            <p className="text-xs text-[#58708F] max-w-xs mt-1 mb-4">
              Create your first project to upload design, order, and acknowledgement files.
            </p>
            <Link href="/projects">
              <Button size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />}>
                Create Project
              </Button>
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-[#DCE6F0]">
            {projects.map((project) => {
              const metaParts = [
                project.customer_name ? `Customer: ${project.customer_name}` : null,
                project.dealer_name ? `Dealer: ${project.dealer_name}` : null,
              ].filter(Boolean);

              return (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className="group flex flex-col sm:flex-row sm:items-center justify-between p-4 px-6 hover:bg-[#F7F9FC] transition-colors gap-2"
                >
                  <div className="flex flex-col space-y-1">
                    <span className="text-sm font-semibold text-[#0F2747] group-hover:text-[#0284C7] transition-colors flex items-center gap-1.5">
                      {project.name}
                      <ArrowUpRight className="h-3.5 w-3.5 opacity-0 group-hover:opacity-100 text-[#0284C7] transition-opacity" />
                    </span>
                    {metaParts.length > 0 ? (
                      <span className="text-xs text-[#58708F]">
                        {metaParts.join(" • ")}
                      </span>
                    ) : (
                      <span className="text-xs text-[#58708F]/70">
                        No customer details specified
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-4 sm:gap-6 justify-between sm:justify-end mt-1 sm:mt-0">
                    <ProjectStatusBadge status={project.status} />
                    <div className="flex items-center gap-2 text-[13px] text-[#58708F] font-normal shrink-0">
                      <span>Updated {formatDate(project.updated_at || project.created_at)}</span>
                      <ChevronRight className="h-4 w-4 text-[#DCE6F0] group-hover:text-[#58708F] transition-colors hidden sm:inline-block" />
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

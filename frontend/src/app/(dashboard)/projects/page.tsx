"use client";

import React, { useState, useMemo } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import {
  useProjects,
  useCreateProject,
  useUpdateProject,
  useDeleteProject,
} from "@/lib/hooks/use-projects";
import { useAuthStore } from "@/lib/store/auth-store";
import { Project, ProjectCreateInput, ProjectUpdateInput } from "@/lib/api/types";
import { ProjectFilters, StatusFilterOption, SortOption, ViewMode } from "@/components/projects/project-filters";
import { ProjectTable } from "@/components/projects/project-table";
import { ProjectCardsList } from "@/components/projects/project-card";
import { ProjectsPageSkeleton } from "@/components/projects/project-skeleton";
import {
  CreateProjectDialog,
  EditProjectDialog,
  DeleteProjectDialog,
} from "@/components/projects/project-dialogs";
import { FolderKanban, Plus, SearchX, FileCheck, GitCompare, CheckCircle2 } from "lucide-react";

export default function ProjectsPage() {
  const { profile } = useAuthStore();
  const userRole = profile?.role || "ADMIN";

  // Data queries & mutations
  const { data: projects = [], isLoading, isError, error, refetch } = useProjects();
  const createMutation = useCreateProject();
  const updateMutation = useUpdateProject();
  const deleteMutation = useDeleteProject();

  // Filters, View Mode & Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilterOption>("ALL");
  const [sortBy, setSortBy] = useState<SortOption>("updated_desc");
  const [viewMode, setViewMode] = useState<ViewMode>("cards");

  // Modal dialog states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deletingProject, setDeletingProject] = useState<Project | null>(null);

  // Calculate status counts from real data
  const statusCounts = useMemo(() => {
    const counts: Record<StatusFilterOption, number> = {
      ALL: projects.length,
      DRAFT: 0,
      PROCESSING: 0,
      REVIEW_REQUIRED: 0,
      COMPLETED: 0,
      FINALIZED: 0,
      FAILED: 0,
    };

    projects.forEach((p) => {
      if (counts[p.status] !== undefined) {
        counts[p.status]++;
      }
    });

    return counts;
  }, [projects]);

  // Filter & sort projects
  const filteredProjects = useMemo(() => {
    let result = [...projects];

    // Status filter
    if (statusFilter !== "ALL") {
      result = result.filter((p) => p.status === statusFilter);
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          (p.customer_name && p.customer_name.toLowerCase().includes(q)) ||
          (p.dealer_name && p.dealer_name.toLowerCase().includes(q))
      );
    }

    // Sort
    result.sort((a, b) => {
      if (sortBy === "updated_desc") {
        return new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime();
      }
      if (sortBy === "updated_asc") {
        return new Date(a.updated_at || a.created_at).getTime() - new Date(b.updated_at || b.created_at).getTime();
      }
      if (sortBy === "name_asc") {
        return a.name.localeCompare(b.name);
      }
      if (sortBy === "name_desc") {
        return b.name.localeCompare(a.name);
      }
      return 0;
    });

    return result;
  }, [projects, statusFilter, searchQuery, sortBy]);

  // Handlers
  const handleCreateSubmit = async (data: ProjectCreateInput) => {
    await createMutation.mutateAsync(data);
  };

  const handleEditSubmit = async (id: string, data: ProjectUpdateInput) => {
    await updateMutation.mutateAsync({ id, data });
  };

  const handleDeleteConfirm = async (id: string) => {
    await deleteMutation.mutateAsync(id);
  };

  const canCreate = userRole === "ADMIN";

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <PageHeader
        title="Projects"
        description="Manage your construction document verification projects."
        actions={
          canCreate ? (
            <Button
              onClick={() => setIsCreateOpen(true)}
              leftIcon={<Plus className="h-4 w-4" />}
            >
              New Project
            </Button>
          ) : undefined
        }
      />

      {/* Loading State */}
      {isLoading && <ProjectsPageSkeleton />}

      {/* Error State */}
      {!isLoading && isError && (
        <ErrorState
          title="Unable to load projects"
          message={error instanceof Error ? error.message : "A network error occurred while retrieving projects."}
          onRetry={() => refetch()}
        />
      )}

      {/* Content State */}
      {!isLoading && !isError && (
        <>
          {projects.length === 0 ? (
            /* Empty State: Workspace has 0 projects */
            <EmptyState
              icon={FolderKanban}
              title="No projects yet"
              description="Create your first project to upload design, order, and acknowledgement documents."
              actionLabel={canCreate ? "Create Project" : undefined}
              onAction={canCreate ? () => setIsCreateOpen(true) : undefined}
            />
          ) : (
            <div className="space-y-6">
              {/* Live Metric Strip */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
                <div className="rounded-xl border border-[#DCE6F0] bg-white p-4 shadow-2xs">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                      Total Projects
                    </span>
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-50 text-[#0EA5E9]">
                      <FolderKanban className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-[#0F2747]">
                      {projects.length}
                    </span>
                    <span className="text-xs font-medium text-[#58708F]">
                      Active
                    </span>
                  </div>
                </div>

                <div className="rounded-xl border border-[#DCE6F0] bg-white p-4 shadow-2xs">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                      Documents Uploaded
                    </span>
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                      <FileCheck className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-[#0F2747]">
                      {projects.reduce((acc, p) => acc + (p.document_count || 0), 0)}
                    </span>
                    <span className="text-xs font-medium text-[#58708F]">
                      / {projects.length * 3} across 3-way
                    </span>
                  </div>
                </div>

                <div className="rounded-xl border border-[#DCE6F0] bg-white p-4 shadow-2xs">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                      Discrepancies
                    </span>
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                      <GitCompare className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-[#0F2747]">
                      {projects.reduce((acc, p) => acc + (p.discrepancy_count || 0), 0)}
                    </span>
                    <span className="text-xs font-medium text-[#58708F]">
                      {projects.reduce(
                        (acc, p) =>
                          acc +
                          Math.max(
                            0,
                            (p.discrepancy_count || 0) -
                              (p.resolved_discrepancy_count || 0)
                          ),
                        0
                      )}{" "}
                      open
                    </span>
                  </div>
                </div>

                <div className="rounded-xl border border-[#DCE6F0] bg-white p-4 shadow-2xs">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-[#58708F] uppercase tracking-wider">
                      Finalized Rate
                    </span>
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                      <CheckCircle2 className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-[#0F2747]">
                      {Math.round(
                        (projects.filter(
                          (p) =>
                            p.status === "FINALIZED" || p.status === "COMPLETED"
                        ).length /
                          (projects.length || 1)) *
                          100
                      )}
                      %
                    </span>
                    <span className="text-xs font-medium text-[#58708F]">
                      {
                        projects.filter(
                          (p) =>
                            p.status === "FINALIZED" || p.status === "COMPLETED"
                        ).length
                      }{" "}
                      completed
                    </span>
                  </div>
                </div>
              </div>

              {/* Search & Filters */}
              <ProjectFilters
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                statusFilter={statusFilter}
                onStatusChange={setStatusFilter}
                sortBy={sortBy}
                onSortChange={setSortBy}
                statusCounts={statusCounts}
                viewMode={viewMode}
                onViewModeChange={setViewMode}
              />

              {/* Filtered 0 results empty state */}
              {filteredProjects.length === 0 ? (
                <div className="rounded-xl border border-[#DCE6F0] bg-white p-12 text-center space-y-3">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-[#F7F9FC] text-[#58708F]">
                    <SearchX className="h-6 w-6" />
                  </div>
                  <h3 className="text-sm font-bold text-[#0F2747]">
                    No matching projects
                  </h3>
                  <p className="text-xs text-[#58708F] max-w-sm mx-auto">
                    No projects match your current search criteria or status filter.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSearchQuery("");
                      setStatusFilter("ALL");
                    }}
                  >
                    Clear Filters
                  </Button>
                </div>
              ) : viewMode === "cards" ? (
                /* Card Grid View */
                <ProjectCardsList
                  projects={filteredProjects}
                  userRole={userRole}
                  onEdit={(p) => setEditingProject(p)}
                  onDelete={(p) => setDeletingProject(p)}
                  forceGrid={true}
                />
              ) : (
                /* Table View */
                <>
                  <ProjectTable
                    projects={filteredProjects}
                    userRole={userRole}
                    onEdit={(p) => setEditingProject(p)}
                    onDelete={(p) => setDeletingProject(p)}
                  />
                  <ProjectCardsList
                    projects={filteredProjects}
                    userRole={userRole}
                    onEdit={(p) => setEditingProject(p)}
                    onDelete={(p) => setDeletingProject(p)}
                  />
                </>
              )}
            </div>
          )}
        </>
      )}

      {/* Modals & Dialogs */}
      <CreateProjectDialog
        open={isCreateOpen}
        onOpenChange={setIsCreateOpen}
        onSubmit={handleCreateSubmit}
        isLoading={createMutation.isPending}
      />

      <EditProjectDialog
        open={!!editingProject}
        project={editingProject}
        onOpenChange={(open) => {
          if (!open) setEditingProject(null);
        }}
        onSubmit={handleEditSubmit}
        isLoading={updateMutation.isPending}
      />

      <DeleteProjectDialog
        open={!!deletingProject}
        project={deletingProject}
        onOpenChange={(open) => {
          if (!open) setDeletingProject(null);
        }}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

"use client";

import React, { useState, useMemo, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/feedback/empty-state";
import { TableLoadingSkeleton } from "@/components/feedback/loading-state";
import { Button } from "@/components/ui/button";
import { useProjects } from "@/lib/hooks/use-projects";
import { useProjectDocuments, useDeleteDocument, useStartProcessing } from "@/lib/hooks/use-documents";
import { useAuthStore } from "@/lib/store/auth-store";
import { Document, Project } from "@/lib/api/types";
import { DocumentSummaryCards } from "@/components/documents/document-summary-cards";
import { DocumentFilterBar, TypeFilterOption, StatusFilterOption } from "@/components/documents/document-filter-bar";
import { DocumentsTable } from "@/components/documents/documents-table";
import { UploadDocumentModal } from "@/components/documents/upload-document-modal";
import { DocumentDetailsDrawer } from "@/components/documents/document-details-drawer";
import { RemoveDocumentDialog } from "@/components/projects/remove-document-dialog";
import { FileText, Upload, SearchX } from "lucide-react";

function DocumentsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlProjectId = searchParams.get("projectId") || "";

  const { profile } = useAuthStore();
  const canManage = profile?.role === "ADMIN" || profile?.role === "REVIEWER";

  // Fetch Projects
  const { data: projects = [], isLoading: isLoadingProjects } = useProjects();

  const projectsMap = useMemo(() => {
    const map: Record<string, Project> = {};
    projects.forEach((p) => {
      map[p.id] = p;
    });
    return map;
  }, [projects]);

  // Selected Project State
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  // Sync selected project with URL or first project available
  useEffect(() => {
    if (urlProjectId && projectsMap[urlProjectId]) {
      setSelectedProjectId(urlProjectId);
    } else if (projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [urlProjectId, projects, projectsMap, selectedProjectId]);

  const handleProjectChange = (id: string) => {
    setSelectedProjectId(id);
    if (id) {
      router.push(`/documents?projectId=${id}`);
    } else {
      router.push("/documents");
    }
  };

  // Fetch Documents for Selected Project
  const {
    data: documents = [],
    isLoading: isLoadingDocs,
    refetch: refetchDocs,
  } = useProjectDocuments(selectedProjectId);

  const deleteDocumentMutation = useDeleteDocument(selectedProjectId);
  const startProcessingMutation = useStartProcessing(selectedProjectId);

  // Filter States
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilterOption>("ALL");
  const [statusFilter, setStatusFilter] = useState<StatusFilterOption>("ALL");

  // Dialog / Drawer States
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedDocDetails, setSelectedDocDetails] = useState<Document | null>(null);
  const [docToDelete, setDocToDelete] = useState<Document | null>(null);

  // Filtered Documents Logic
  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      // Search
      if (searchQuery.trim() !== "") {
        const query = searchQuery.toLowerCase();
        const filename = (doc.original_filename || doc.filename || "").toLowerCase();
        if (!filename.includes(query)) return false;
      }

      // Type Filter
      if (typeFilter !== "ALL" && doc.document_type !== typeFilter) {
        return false;
      }

      // Status Filter
      if (statusFilter !== "ALL") {
        if (statusFilter === "READY" && doc.status !== "COMPLETED") return false;
        if (statusFilter === "PROCESSING" && doc.status !== "PROCESSING" && doc.status !== "UPLOADED") return false;
        if (statusFilter === "FAILED" && doc.status !== "FAILED") return false;
      }

      return true;
    });
  }, [documents, searchQuery, typeFilter, statusFilter]);

  const handleResetFilters = () => {
    setSearchQuery("");
    setTypeFilter("ALL");
    setStatusFilter("ALL");
  };

  const handleDeleteConfirm = async (docId: string) => {
    await deleteDocumentMutation.mutateAsync(docId);
    setDocToDelete(null);
    refetchDocs();
  };

  const handleReprocessDoc = async () => {
    await startProcessingMutation.mutateAsync();
    refetchDocs();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Documents"
        description="Manage Design, Purchase Order, and Manufacturer Acknowledgement documents."
        actions={
          <Button
            onClick={() => setIsUploadModalOpen(true)}
            leftIcon={<Upload className="h-4 w-4" />}
            disabled={projects.length === 0}
          >
            Upload Document
          </Button>
        }
      />

      {/* Filter Bar & Project Selector */}
      <DocumentFilterBar
        projects={projects}
        selectedProjectId={selectedProjectId}
        onProjectChange={handleProjectChange}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        typeFilter={typeFilter}
        onTypeFilterChange={setTypeFilter}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        onResetFilters={handleResetFilters}
        totalResultsCount={filteredDocuments.length}
      />

      {/* Main Content Area */}
      {isLoadingProjects || (selectedProjectId && isLoadingDocs) ? (
        <TableLoadingSkeleton rows={5} />
      ) : !selectedProjectId ? (
        /* Empty State: No Project Selected */
        <EmptyState
          icon={FileText}
          title="Select a project"
          description="Choose a project to view and manage its Design, Purchase Order, and Manufacturer Acknowledgement documents."
          actionLabel="Select Project"
          onAction={() => {
            if (projects.length > 0) {
              handleProjectChange(projects[0].id);
            } else {
              router.push("/projects");
            }
          }}
        />
      ) : documents.length === 0 ? (
        /* Empty State: Selected Project Has No Documents */
        <EmptyState
          icon={FileText}
          title="No documents yet"
          description="Upload the Design, Purchase Order, or Manufacturer Acknowledgement for this project to begin your CrossCheck."
          actionLabel="Upload Document"
          onAction={() => setIsUploadModalOpen(true)}
        />
      ) : (
        <div className="space-y-5">
          {/* Compact Summary Cards */}
          <DocumentSummaryCards documents={documents} isLoading={isLoadingDocs} />

          {/* Document Table / Card View */}
          {filteredDocuments.length === 0 ? (
            <EmptyState
              icon={SearchX}
              title="No matching documents found"
              description="Try adjusting your search query or clear your current document filters."
              actionLabel="Reset Filters"
              onAction={handleResetFilters}
            />
          ) : (
            <DocumentsTable
              documents={filteredDocuments}
              projectsMap={projectsMap}
              onViewDetails={(doc) => setSelectedDocDetails(doc)}
              onDeleteDoc={(doc) => setDocToDelete(doc)}
              canManage={canManage}
            />
          )}
        </div>
      )}

      {/* Upload Document Modal */}
      <UploadDocumentModal
        open={isUploadModalOpen}
        projects={projects}
        defaultProjectId={selectedProjectId}
        onOpenChange={setIsUploadModalOpen}
        onSuccess={(projId) => {
          handleProjectChange(projId);
          refetchDocs();
        }}
      />

      {/* Document Details Drawer / Dialog */}
      <DocumentDetailsDrawer
        open={Boolean(selectedDocDetails)}
        document={selectedDocDetails}
        project={selectedDocDetails ? projectsMap[selectedDocDetails.project_id] : null}
        onOpenChange={(open) => {
          if (!open) setSelectedDocDetails(null);
        }}
        onDelete={async (docId) => {
          await deleteDocumentMutation.mutateAsync(docId);
          setSelectedDocDetails(null);
          refetchDocs();
        }}
        onReprocess={handleReprocessDoc}
        canManage={canManage}
      />

      {/* Delete Document Confirmation Dialog */}
      {docToDelete && (
        <RemoveDocumentDialog
          open={Boolean(docToDelete)}
          document={docToDelete}
          documentTitle={docToDelete.original_filename || docToDelete.filename || "Document"}
          onOpenChange={(open) => {
            if (!open) setDocToDelete(null);
          }}
          onConfirm={handleDeleteConfirm}
          isLoading={deleteDocumentMutation.isPending}
        />
      )}
    </div>
  );
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<TableLoadingSkeleton rows={5} />}>
      <DocumentsContent />
    </Suspense>
  );
}

"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useProject } from "@/lib/hooks/use-projects";
import {
  useProjectDocuments,
  useUploadDocument,
  useDeleteDocument,
  useStartProcessing,
  useJobStatus,
  useCancelJob,
  useLatestJob,
} from "@/lib/hooks/use-documents";
import { useAuthStore } from "@/lib/store/auth-store";
import { ProjectDetailHeader } from "@/components/projects/project-detail-header";
import { ProjectDocumentWorkflow } from "@/components/projects/project-document-workflow";
import { ProjectDocumentCard } from "@/components/projects/project-document-card";
import { ProcessingStatusCard } from "@/components/projects/processing-status-card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/feedback/error-state";
import { DocumentType, ProcessingJobResponse } from "@/lib/api/types";
import { ArrowLeft, AlertCircle } from "lucide-react";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = (params?.projectId as string) || "";

  const { profile } = useAuthStore();
  const userRole = profile?.role || "VIEWER";
  const {
    data: project,
    isLoading: isProjectLoading,
    error: projectError,
    refetch: refetchProject,
  } = useProject(projectId);
  
  const isFinalized = project?.status === "FINALIZED";
  const canManage = (userRole === "ADMIN" || userRole === "REVIEWER") && !isFinalized;

  // Documents Queries
  const {
    data: documents = [],
    isLoading: isDocsLoading,
    refetch: refetchDocs,
  } = useProjectDocuments(projectId);

  // Mutations
  const uploadMutation = useUploadDocument(projectId);
  const deleteMutation = useDeleteDocument(projectId);
  const processMutation = useStartProcessing(projectId);
  const cancelMutation = useCancelJob(projectId);

  // Active Job & Polling
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isStatusCardDismissed, setIsStatusCardDismissed] = useState(false);
  const { data: jobStatusData } = useJobStatus(
    activeJobId,
    Boolean(activeJobId)
  );

  // Recover the active job id after a page reload/navigation, so Cancel/Retry
  // keep working even when this component remounted mid-processing.
  const { data: latestJobData } = useLatestJob(
    projectId,
    !activeJobId && project?.status === "PROCESSING"
  );
  useEffect(() => {
    if (!activeJobId && latestJobData?.id) {
      setActiveJobId(latestJobData.id);
    }
  }, [activeJobId, latestJobData]);

  // Uploading state per document type
  const [uploadingType, setUploadingType] = useState<DocumentType | null>(null);
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Map uploaded documents by type
  const designDoc = documents.find((d) => d.document_type === "DESIGN") || null;
  const orderDoc = documents.find((d) => d.document_type === "ORDER") || null;
  const ackDoc =
    documents.find((d) => d.document_type === "ACKNOWLEDGEMENT") || null;

  const isAllUploaded = Boolean(designDoc && orderDoc && ackDoc);
  const isProcessing =
    processMutation.isPending ||
    (Boolean(jobStatusData) &&
      jobStatusData?.status !== "COMPLETED" &&
      jobStatusData?.status !== "FAILED") ||
    project?.status === "PROCESSING";

  // Handlers
  const handleUpload = async (type: DocumentType, file: File) => {
    setActionError(null);
    setUploadingType(type);
    try {
      await uploadMutation.mutateAsync({ documentType: type, file });
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : "Upload failed. Please try again."
      );
      throw err;
    } finally {
      setUploadingType(null);
    }
  };

  const handleDelete = async (documentId: string) => {
    setActionError(null);
    setDeletingDocId(documentId);
    try {
      await deleteMutation.mutateAsync(documentId);
    } catch (err: unknown) {
      setActionError(
        err instanceof Error
          ? err.message
          : "Failed to remove document. Please try again."
      );
      throw err;
    } finally {
      setDeletingDocId(null);
    }
  };

  const handleCancelProcessing = async () => {
    if (!activeJobId) return;
    setActionError(null);
    try {
      await cancelMutation.mutateAsync(activeJobId);
    } catch (err: unknown) {
      setActionError(
        err instanceof Error
          ? err.message
          : "Failed to cancel processing. Please try again."
      );
    }
  };

  const handleStartCrossCheck = async () => {
    setActionError(null);
    setIsStatusCardDismissed(false);
    try {
      const job: ProcessingJobResponse = await processMutation.mutateAsync();
      if (job?.id) {
        setActiveJobId(job.id);
      }
    } catch (err: unknown) {
      setActionError(
        err instanceof Error
          ? err.message
          : "Cross-check could not be started."
      );
    }
  };

  // Loading skeleton
  if (isProjectLoading || isDocsLoading) {
    return (
      <div className="space-y-6 pb-12">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-36 rounded-xl" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </div>
    );
  }

  // Error state
  if (projectError || !project) {
    return (
      <div className="space-y-6 pb-12">
        <Link
          href="/projects"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#58708F] hover:text-[#0F2747]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Projects
        </Link>
        <ErrorState
          title="Project not found"
          message={
            projectError instanceof Error
              ? projectError.message
              : "Could not load details for this project. It may have been deleted or belong to another organization."
          }
          onRetry={() => {
            refetchProject();
            refetchDocs();
          }}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Project Detail Header */}
      <ProjectDetailHeader
        project={project}
        canProcess={canManage}
        isAllUploaded={isAllUploaded}
        isProcessing={isProcessing}
        onStartCrossCheck={handleStartCrossCheck}
        canEdit={canManage}
      />

      {/* Action Error Alert */}
      {actionError && (
        <div className="flex items-start gap-2.5 rounded-xl border border-[#FECACA] bg-[#FEE2E2] p-4 text-xs text-[#B91C1C]">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Action Notice: </span>
            <span>{actionError}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="text-[#B91C1C] hover:opacity-80 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* 2. Active Pipeline Processing Status Card */}
      {!isStatusCardDismissed &&
        (isProcessing ||
          jobStatusData?.status === "COMPLETED" ||
          jobStatusData?.status === "FAILED") && (
          <ProcessingStatusCard
            status={jobStatusData?.status || "QUEUED"}
            error={jobStatusData?.error}
            projectId={projectId}
            onRetry={handleStartCrossCheck}
            onDismiss={() => setIsStatusCardDismissed(true)}
            onCancel={handleCancelProcessing}
            isCancelling={cancelMutation.isPending}
          />
        )}

      {/* 3. Document Verification Workflow Step Tracker */}
      <ProjectDocumentWorkflow documents={documents} />

      {/* 4. Three-Way Document Upload Cards */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-sm font-bold text-[#0F2747]">
            Required Verification Documents
          </h2>
          <span className="text-xs text-[#58708F]">
            {isAllUploaded
              ? "All 3 documents uploaded"
              : "Upload all three required documents to start verification"}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Design Document Card */}
          <ProjectDocumentCard
            documentType="DESIGN"
            projectId={projectId}
            document={designDoc}
            onUpload={handleUpload}
            onDelete={handleDelete}
            isUploading={uploadingType === "DESIGN"}
            isDeleting={deletingDocId === designDoc?.id}
            canManage={canManage}
          />

          {/* Purchase Order Card */}
          <ProjectDocumentCard
            documentType="ORDER"
            projectId={projectId}
            document={orderDoc}
            onUpload={handleUpload}
            onDelete={handleDelete}
            isUploading={uploadingType === "ORDER"}
            isDeleting={deletingDocId === orderDoc?.id}
            canManage={canManage}
          />

          {/* Manufacturer Acknowledgement Card */}
          <ProjectDocumentCard
            documentType="ACKNOWLEDGEMENT"
            projectId={projectId}
            document={ackDoc}
            onUpload={handleUpload}
            onDelete={handleDelete}
            isUploading={uploadingType === "ACKNOWLEDGEMENT"}
            isDeleting={deletingDocId === ackDoc?.id}
            canManage={canManage}
          />
        </div>
      </div>
    </div>
  );
}


import { apiClient } from "./client";
import {
  UserProfile,
  RegisterInput,
  RegisterResponse,
  LoginInput,
  TokenResponse,
  VerifyEmailInput,
  ResendVerificationInput,
  ForgotPasswordInput,
  ResetPasswordInput,
  GoogleCallbackInput,
  GoogleAuthUrlResponse,
  MessageResponse,
  Project,
  ProjectCreateInput,
  ProjectUpdateInput,
  Document,
  DocumentType,
  ProcessingJobResponse,
  ProcessingStatus,
  CrossCheckResult,
  Report,
  ReviewActionRequest,
  AuditLog,
  Organization,
  OrganizationUpdateInput,
  Manufacturer,
  ManufacturerCreateInput,
  ManufacturerUpdateInput,
  ManufacturerCode,
  ManufacturerCodeCreateInput,
  ManufacturerCodeUpdateInput,
  BulkImportPreview,
  BulkImportResult,
  SpecBook,
  SpecBookRow,
  SpecBookRowStatus,
  SpecBookRowUpdateInput,
  ApproveRowsRequest,
  ApproveRowsResult,
  NKBAReferenceDocument,
} from "./types";

export const authApi = {
  register: (data: RegisterInput) =>
    apiClient.post<RegisterResponse>("/auth/register", data),

  login: (data: LoginInput) =>
    apiClient.post<TokenResponse>("/auth/login", data),

  verifyEmail: (data: VerifyEmailInput) =>
    apiClient.post<MessageResponse>("/auth/verify-email", data),

  resendVerification: (data: ResendVerificationInput) =>
    apiClient.post<MessageResponse>("/auth/resend-verification", data),

  forgotPassword: (data: ForgotPasswordInput) =>
    apiClient.post<MessageResponse>("/auth/forgot-password", data),

  resetPassword: (data: ResetPasswordInput) =>
    apiClient.post<MessageResponse>("/auth/reset-password", data),

  getGoogleAuthUrl: () =>
    apiClient.get<GoogleAuthUrlResponse>("/auth/google/url"),

  googleCallback: (data: GoogleCallbackInput) =>
    apiClient.post<TokenResponse>("/auth/google/callback", data),

  getMe: () =>
    apiClient.get<UserProfile>("/users/me"),
};

export const projectsApi = {
  list: () => apiClient.get<Project[]>("/projects"),
  get: (id: string) => apiClient.get<Project>(`/projects/${id}`),
  create: (data: ProjectCreateInput) =>
    apiClient.post<Project>("/projects", data),
  update: (id: string, data: ProjectUpdateInput) =>
    apiClient.patch<Project>(`/projects/${id}`, data),
  delete: (id: string) => apiClient.delete<void>(`/projects/${id}`),
};

export const documentsApi = {
  list: (projectId: string) =>
    apiClient.get<Document[]>(`/projects/${projectId}/documents`),
  upload: (projectId: string, documentType: DocumentType, file: File) => {
    const formData = new FormData();
    formData.append("document_type", documentType);
    formData.append("file", file);
    return apiClient.upload<Document>(
      `/projects/${projectId}/documents`,
      formData
    );
  },
  getUrl: (projectId: string, documentId: string) =>
    apiClient.get<{ url: string }>(
      `/projects/${projectId}/documents/${documentId}`
    ),
  delete: (projectId: string, documentId: string) =>
    apiClient.delete<void>(`/projects/${projectId}/documents/${documentId}`),
};

export const processingApi = {
  start: (projectId: string) =>
    apiClient.post<ProcessingJobResponse>(`/projects/${projectId}/process`),
  jobStatus: (jobId: string) =>
    apiClient.get<ProcessingJobResponse>(`/jobs/${jobId}/status`),
  cancel: (jobId: string) =>
    apiClient.post<ProcessingJobResponse>(`/jobs/${jobId}/cancel`),
  latestJob: (projectId: string) =>
    apiClient.get<ProcessingJobResponse>(`/projects/${projectId}/jobs/latest`),
  status: (projectId: string) =>
    apiClient.get<ProcessingStatus>(`/projects/${projectId}/processing/status`),
};

export const crosscheckApi = {
  get: (projectId: string) =>
    apiClient.get<CrossCheckResult>(`/projects/${projectId}/crosscheck`),
};

export const reviewApi = {
  submitAction: (discrepancyId: string, data: ReviewActionRequest) =>
    apiClient.post<{ status: string; discrepancy_id?: string; match_group_id?: string; new_status?: string }>(
      `/discrepancies/${discrepancyId}/review`,
      data
    ),
  finalize: (projectId: string) =>
    apiClient.post<Project>(`/projects/${projectId}/finalize`),
  bulkAcceptNonCritical: (projectId: string, reason?: string) =>
    apiClient.post<{ status: string; accepted_count: number }>(
      `/projects/${projectId}/discrepancies/bulk-accept`,
      { reason }
    ),
  getAuditLogs: (projectId: string) =>
    apiClient.get<AuditLog[]>(`/projects/${projectId}/audit-logs`),
};

export const reportsApi = {
  list: (projectId: string) =>
    apiClient.get<Report[]>(`/projects/${projectId}/reports`),
  create: (projectId: string, data: { format: string }) =>
    apiClient.post<Report>(`/projects/${projectId}/reports`, data),
  status: (reportId: string) =>
    apiClient.get<Report>(`/reports/${reportId}/status`),
  download: (reportId: string) =>
    apiClient.get<{ download_url: string }>(`/reports/${reportId}/download`),
  downloadCsvUrl: (projectId: string) => {
    // Generate the URL directly, we will use it in an anchor tag
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    return `${baseUrl}/projects/${projectId}/reports/csv`;
  },
  downloadPdfUrl: (projectId: string) => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    return `${baseUrl}/projects/${projectId}/reports/pdf`;
  },
};

export const usersApi = {
  getMe: () => apiClient.get<UserProfile>("/users/me"),
  updateMe: (data: { full_name?: string }) =>
    apiClient.patch<UserProfile>("/users/me", data),
  changePassword: (data: { current_password?: string; new_password: string }) =>
    apiClient.post<{ message: string }>("/users/me/change-password", data),
};

export const organizationsApi = {
  getMe: () => apiClient.get<Organization>("/organizations/me"),
  updateMe: (data: OrganizationUpdateInput) =>
    apiClient.patch<Organization>("/organizations/me", data),
};

export const manufacturersApi = {
  list: () => apiClient.get<Manufacturer[]>("/manufacturers"),
  create: (data: ManufacturerCreateInput) =>
    apiClient.post<Manufacturer>("/manufacturers", data),
  update: (id: string, data: ManufacturerUpdateInput) =>
    apiClient.patch<Manufacturer>(`/manufacturers/${id}`, data),

  listCodes: (manufacturerId: string, params?: { search?: string; category?: string }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.category) qs.set("category", params.category);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiClient.get<ManufacturerCode[]>(`/manufacturers/${manufacturerId}/codes${suffix}`);
  },
  createCode: (manufacturerId: string, data: ManufacturerCodeCreateInput) =>
    apiClient.post<ManufacturerCode>(`/manufacturers/${manufacturerId}/codes`, data),
  updateCode: (manufacturerId: string, codeId: string, data: ManufacturerCodeUpdateInput) =>
    apiClient.patch<ManufacturerCode>(`/manufacturers/${manufacturerId}/codes/${codeId}`, data),
  deactivateCode: (manufacturerId: string, codeId: string) =>
    apiClient.post<ManufacturerCode>(`/manufacturers/${manufacturerId}/codes/${codeId}/deactivate`, {}),
  deleteCode: (manufacturerId: string, codeId: string) =>
    apiClient.delete<void>(`/manufacturers/${manufacturerId}/codes/${codeId}`),

  previewImport: (manufacturerId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.upload<BulkImportPreview>(`/manufacturers/${manufacturerId}/codes/import/preview`, formData);
  },
  commitImport: (manufacturerId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.upload<BulkImportResult>(`/manufacturers/${manufacturerId}/codes/import/commit`, formData);
  },

  uploadSpecBook: (manufacturerId: string, file: File, sourceVersion?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    if (sourceVersion) formData.append("source_version", sourceVersion);
    return apiClient.upload<SpecBook>(`/manufacturers/${manufacturerId}/spec-books`, formData);
  },
  listSpecBooks: (manufacturerId: string) =>
    apiClient.get<SpecBook[]>(`/manufacturers/${manufacturerId}/spec-books`),
  getSpecBook: (manufacturerId: string, bookId: string) =>
    apiClient.get<SpecBook>(`/manufacturers/${manufacturerId}/spec-books/${bookId}`),
  listSpecBookRows: (manufacturerId: string, bookId: string, status?: SpecBookRowStatus) => {
    const qs = status ? `?status=${status}` : "";
    return apiClient.get<SpecBookRow[]>(`/manufacturers/${manufacturerId}/spec-books/${bookId}/rows${qs}`);
  },
  updateSpecBookRow: (manufacturerId: string, bookId: string, rowId: string, data: SpecBookRowUpdateInput) =>
    apiClient.patch<SpecBookRow>(`/manufacturers/${manufacturerId}/spec-books/${bookId}/rows/${rowId}`, data),
  rejectSpecBookRow: (manufacturerId: string, bookId: string, rowId: string) =>
    apiClient.post<SpecBookRow>(`/manufacturers/${manufacturerId}/spec-books/${bookId}/rows/${rowId}/reject`, {}),
  approveSpecBookRows: (manufacturerId: string, bookId: string, data: ApproveRowsRequest) =>
    apiClient.post<ApproveRowsResult>(`/manufacturers/${manufacturerId}/spec-books/${bookId}/approve`, data),
};

export const nkbaReferenceApi = {
  list: () => apiClient.get<NKBAReferenceDocument[]>("/nkba-reference-documents"),
  upload: (file: File, label: string) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("label", label);
    return apiClient.upload<NKBAReferenceDocument>("/nkba-reference-documents", formData);
  },
  getDownloadUrl: (id: string) => apiClient.get<{ url: string }>(`/nkba-reference-documents/${id}/download-url`),
  delete: (id: string) => apiClient.delete<void>(`/nkba-reference-documents/${id}`),
};



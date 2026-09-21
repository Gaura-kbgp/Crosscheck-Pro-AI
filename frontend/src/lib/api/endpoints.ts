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



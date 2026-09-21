export type Role = "ADMIN" | "REVIEWER" | "VIEWER";

export type ProjectStatus =
  | "DRAFT"
  | "PROCESSING"
  | "REVIEW_REQUIRED"
  | "COMPLETED"
  | "FINALIZED"
  | "FAILED";

export type DocumentType = "DESIGN" | "ORDER" | "ACKNOWLEDGEMENT";

export type DocumentStatus = "UPLOADED" | "PROCESSING" | "COMPLETED" | "FAILED";

export type CrossCheckStatus =
  | "MATCHED"
  | "CHANGED"
  | "MISSING"
  | "EXTRA"
  | "UNCERTAIN";

export type ReviewStatus =
  | "OPEN"
  | "ACCEPTED"
  | "FALSE_POSITIVE"
  | "ESCALATED"
  | "ACKNOWLEDGED";

export type Severity = "CRITICAL" | "HIGH" | "WARNING" | "INFO";

export type ItemCategory =
  | "CABINET"
  | "ACCESSORY"
  | "FILLER"
  | "PANEL"
  | "MOLDING"
  | "APPLIANCE"
  | "ARCHITECTURAL_ANNOTATION"
  | "COMMERCIAL_CHARGE"
  | "UNKNOWN";

export type ProcessingStage =
  | "QUEUED"
  | "VALIDATING"
  | "EXTRACTING"
  | "NORMALIZING"
  | "MATCHING"
  | "COMPARING"
  | "GENERATING_DISCREPANCIES"
  | "COMPLETED"
  | "FAILED";

export type ReportFormat = "PDF" | "CSV";

export type ReportStatus = "QUEUED" | "GENERATING" | "COMPLETED" | "FAILED";

// Auth API Models
export interface UserProfile {
  id: string;
  auth_id?: string | null;
  organization_id: string;
  email: string;
  full_name?: string | null;
  role: Role;
  is_verified?: boolean;
  created_at: string;
  updated_at: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  confirm_password?: string;
  full_name?: string;
}

export interface RegisterResponse {
  message: string;
  email: string;
  is_verified: boolean;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface VerifyEmailInput {
  token: string;
}

export interface ResendVerificationInput {
  email: string;
}

export interface ForgotPasswordInput {
  email: string;
}

export interface ResetPasswordInput {
  token: string;
  new_password: string;
  confirm_password?: string;
}

export interface GoogleCallbackInput {
  code: string;
}

export interface GoogleAuthUrlResponse {
  url: string;
}

export interface MessageResponse {
  message: string;
}

// Project API Models
export interface Project {
  id: string;
  organization_id: string;
  name: string;
  customer_name?: string | null;
  dealer_name?: string | null;
  status: ProjectStatus;
  document_count?: number;
  uploaded_document_types?: string[];
  discrepancy_count?: number;
  resolved_discrepancy_count?: number;
  progress_percentage?: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateInput {
  name: string;
  customer_name?: string;
  dealer_name?: string;
}

export interface ProjectUpdateInput {
  name?: string;
  customer_name?: string;
  dealer_name?: string;
  status?: ProjectStatus;
}

export interface Document {
  id: string;
  project_id: string;
  organization_id: string;
  document_type: DocumentType;
  original_filename?: string;
  filename?: string;
  mime_type?: string;
  file_size?: number;
  storage_path?: string;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
}

export interface ProcessingJobResponse {
  id: string;
  project_id: string;
  organization_id: string;
  status: ProcessingStage;
  error?: Record<string, unknown> | null;
  correlation_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProcessingStatus {
  project_id: string;
  status: ProjectStatus;
  stage: ProcessingStage;
  progress_pct: number;
  message?: string | null;
  error?: Record<string, unknown> | null;
}

export interface Discrepancy {
  id: string;
  match_group_id: string;
  field_name: string;
  design_value?: string | null;
  order_value?: string | null;
  ack_value?: string | null;
  severity: Severity;
  introduced_at?: string | null;
  status: ReviewStatus;
  explanation?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MatchGroup {
  id: string;
  project_id: string;
  canonical_sku: string;
  canonical_item_id: string | null;
  status: CrossCheckStatus;
  final_sku?: string | null;
  final_quantity?: number | null;
  final_dimensions?: string | null;
  final_finish?: string | null;
  final_door_style?: string | null;
  final_modifications?: string | null;
  final_unit_price?: number | null;
  final_total_price?: number | null;
  discrepancies: Discrepancy[];
}

export interface CrossCheckResult {
  project_id: string;
  groups: MatchGroup[];
  summary: {
    total_groups: number;
    matched: number;
    changed: number;
    missing: number;
    extra: number;
    uncertain: number;
    critical_discrepancies: number;
    open_reviews: number;
  };
}

export interface Report {
  id: string;
  project_id: string;
  organization_id: string;
  format: ReportFormat;
  status: ReportStatus;
  storage_path?: string | null;
  download_url?: string | null;
  error?: Record<string, unknown> | null;
  created_at: string;
  completed_at?: string | null;
}

export interface ApiError {
  detail: string;
  status?: number;
  code?: string;
}

export type ReviewActionType =
  | "ACCEPT_FINDING"
  | "FALSE_POSITIVE"
  | "ESCALATE"
  | "ACKNOWLEDGE_MFR_CHANGE"
  | "OVERRIDE_DATA";

export interface ReviewActionRequest {
  action: ReviewActionType;
  reason?: string;
  match_group_id?: string;
  canonical_item_id?: string;
  field_name?: string;
  new_value?: unknown;
}

export interface AuditLog {
  id: string;
  project_id: string;
  actor_id?: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  previous_state?: Record<string, unknown> | null;
  new_state?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  settings?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  user_count?: number;
  project_count?: number;
}

export interface OrganizationUpdateInput {
  name?: string;
  settings?: Record<string, unknown>;
}

export interface UserUpdateInput {
  full_name?: string;
}

export interface ChangePasswordInput {
  current_password?: string;
  new_password: string;
}

export interface LocalPreferences {
  defaultProjectView: "grid" | "table";
  defaultCrossCheckView: "all" | "discrepancies_only";
  density: "comfortable" | "compact";
  confirmDestructiveActions: boolean;
  autoRefreshInterval: number; // in seconds (0 = disabled, 3, 5, 10)
  theme: "system" | "light" | "dark";
}

export interface NotificationSettings {
  processingCompleted: boolean;
  processingFailed: boolean;
  reviewRequired: boolean;
  criticalDiscrepancyDetected: boolean;
  reportGenerated: boolean;
  projectFinalized: boolean;
  emailDigest: "instant" | "daily" | "weekly" | "disabled";
}


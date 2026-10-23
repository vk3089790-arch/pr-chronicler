/**
 * TypeScript type definitions for PR Chronicler API responses and entities.
 */

export type DeliveryStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "IGNORED";
export type EmailStatus = "SENT" | "FAILED" | "NOT_SENT";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface SystemStatusSummary {
  status: "healthy" | "degraded";
  gemini_model: string;
  gemini_effective_model: string;
  gemini_configured: boolean;
  github_token_configured: boolean;
  smtp_configured: boolean;
  webhook_secret_enforced: boolean;
  database: string;
}

export interface RecentActivityItem {
  delivery_id: string;
  repo: string;
  pr_number: number;
  pr_title: string;
  pr_author: string;
  action: string;
  status: DeliveryStatus;
  created_at: string;
  updated_at: string;
}

export interface RecentErrorItem {
  delivery_id: string;
  repo: string;
  pr_number: number;
  pr_title: string;
  error_message: string;
  updated_at: string;
}

export interface DashboardSummary {
  total_prs: number;
  total_deliveries: number;
  completed_jobs: number;
  failed_jobs: number;
  ignored_jobs: number;
  processing_jobs: number;
  total_learnings: number;
  total_emails_sent: number;
  status_distribution: Record<string, number>;
  recent_activity: RecentActivityItem[];
  recent_errors: RecentErrorItem[];
  last_successful_processing_at: string | null;
  system_status: SystemStatusSummary;
}

export interface PullRequestItem {
  delivery_id: string;
  repo: string;
  pr_number: number;
  action: string;
  status: DeliveryStatus;
  reason: string | null;
  created_at: string;
  updated_at: string;
  reflection_json: string | null;
  error_message: string | null;
  pr_title: string;
  pr_author: string;
  pr_url: string;
  learnings_count: number;
  email_status: EmailStatus;
}

export interface ParsedReflection {
  issue_details: string;
  execution_summary: string;
  key_learnings: string[];
}

export interface EmailLogItem {
  id: number;
  recipient: string;
  subject: string;
  status: "SENT" | "FAILED";
  error_message: string | null;
  sent_at: string;
}

export interface PullRequestDetail extends PullRequestItem {
  reflection: ParsedReflection | null;
  emails: EmailLogItem[];
}

export interface LearningItem {
  id: string;
  delivery_id: string;
  repo: string;
  pr_number: number;
  pr_title: string;
  pr_url: string;
  pr_author: string | null;
  learning: string;
  index: number;
  evidence_tags: string[];
  created_at: string;
  execution_summary_snippet: string | null;
  issue_details_snippet: string | null;
}

export interface WebhookEventItem {
  delivery_id: string;
  repo: string;
  pr_number: number;
  action: string;
  status: DeliveryStatus;
  reason: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  pr_title: string | null;
  pr_author: string | null;
  pr_url: string | null;
}

export interface EmailDeliveryItem {
  id: number;
  delivery_id: string;
  repo: string;
  pr_number: number;
  recipient: string;
  subject: string;
  status: "SENT" | "FAILED";
  error_message: string | null;
  sent_at: string;
}

export interface SystemHealthData {
  status: "healthy" | "degraded";
  service: string;
  version: string;
  database: {
    path: string;
    connected: boolean;
    wal_mode: boolean;
    total_deliveries: number;
  };
  gemini: {
    configured: boolean;
    model: string;
    effective_model: string;
    temperature: number;
  };
  github: {
    token_configured: boolean;
  };
  smtp: {
    configured: boolean;
    host: string;
    port: number;
    use_tls: boolean;
    recipient_configured: boolean;
  };
  webhook_security: {
    secret_enforced: boolean;
  };
  last_successful_processing_at: string | null;
  counts: {
    completed: number;
    failed: number;
    ignored: number;
    learnings: number;
    emails_sent: number;
  };
}

export interface SettingsData {
  environment: {
    host: string;
    port: number;
    database_path: string;
    log_file: string;
    log_level: string;
  };
  gemini: {
    model: string;
    temperature: number;
    api_key_configured: boolean;
  };
  github: {
    token_configured: boolean;
    webhook_secret_configured: boolean;
  };
  smtp: {
    host: string;
    port: number;
    use_tls: boolean;
    sender_email_masked: string;
    recipient_email_masked: string;
    app_password_configured: boolean;
  };
  operational_guidance: {
    config_method: string;
    secrets_policy: string;
    background_workers: string;
  };
}

// =====================================================================
// Explorer & Outreach Interfaces
// =====================================================================

export interface RecentSearchItem {
  id: number;
  query: string;
  search_type: "user" | "repo";
  target: string;
  created_at: string;
}

export interface ContributorProfile {
  login: string;
  id?: number;
  avatar_url?: string;
  html_url: string;
  name?: string;
  company?: string;
  blog?: string;
  location?: string;
  email?: string;
  bio?: string;
  twitter_username?: string;
  public_repos: number;
  public_gists: number;
  followers: number;
  following: number;
  created_at?: string;
}

export interface RepositoryMetadata {
  name: string;
  full_name: string;
  owner?: {
    login: string;
    avatar_url?: string;
  };
  html_url: string;
  description?: string;
  stargazers_count: number;
  forks_count: number;
  open_issues_count: number;
  language?: string;
  topics?: string[];
  default_branch?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ExplorerPRItem {
  number: number;
  title: string;
  html_url: string;
  state: string;
  created_at: string;
  updated_at?: string;
  closed_at?: string;
  merged_at?: string;
  user?: {
    login: string;
    avatar_url?: string;
  };
  repo_full_name?: string;
  is_analyzed?: boolean;
  is_saved?: boolean;
}

export interface ExplorerChangedFile {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  changes: number;
  patch?: string;
}

export interface ExplorerPRDetail {
  pr: {
    number: number;
    title: string;
    body?: string;
    html_url: string;
    state: string;
    merged_at?: string;
    created_at: string;
    user?: {
      login: string;
      avatar_url?: string;
    };
  };
  files: ExplorerChangedFile[];
  total_patch_char_count: number;
  reflection: ParsedReflection | null;
  is_saved: boolean;
}

export interface SavedContributionItem {
  id: number;
  repo: string;
  pr_number: number;
  pr_title: string;
  pr_author: string;
  pr_url: string;
  state: string;
  merged_at?: string;
  created_at: string;
  updated_at: string;
  analyzed_at?: string;
  is_analyzed: boolean;
  is_saved: boolean;
}

export interface OutreachDraftRequest {
  contributor_username: string;
  recipient_email?: string;
  repo?: string;
  pr_number?: number;
  pr_title?: string;
  email_source?: string;
}

export interface OutreachDraftResponse {
  recipient?: string;
  recipient_masked?: string;
  email_source: string;
  subject: string;
  body: string;
}

export interface OutreachSendRequest {
  recipient_email: string;
  subject: string;
  body: string;
  contributor_username?: string;
  repo?: string;
  pr_number?: number;
  email_source?: string;
  idempotency_key: string;
  confirm_send: boolean;
}

export interface OutreachRecordItem {
  id: number;
  recipient_masked: string;
  contributor_username?: string;
  repo?: string;
  pr_number?: number;
  subject: string;
  body_snippet: string;
  status: "SENT" | "FAILED";
  email_source: string;
  error_message?: string;
  sent_at?: string;
  created_at: string;
  idempotency_key: string;
}


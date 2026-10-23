/**
 * Centralized API client for communicating with PR Chronicler backend.
 */

import {
  ContributorProfile,
  DashboardSummary,
  EmailDeliveryItem,
  ExplorerPRDetail,
  ExplorerPRItem,
  LearningItem,
  OutreachDraftRequest,
  OutreachDraftResponse,
  OutreachRecordItem,
  OutreachSendRequest,
  PaginatedResponse,
  ParsedReflection,
  PullRequestDetail,
  PullRequestItem,
  RecentSearchItem,
  RepositoryMetadata,
  SavedContributionItem,
  SettingsData,
  SystemHealthData,
  WebhookEventItem,
} from "./types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string, public details?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  
  const headers = new Headers(options.headers || {});
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  try {
    const res = await fetch(url, {
      ...options,
      headers,
      cache: "no-store",
    });

    if (!res.ok) {
      let errorDetail: unknown;
      try {
        errorDetail = await res.json();
      } catch {
        errorDetail = await res.text();
      }
      const message =
        typeof errorDetail === "object" && errorDetail && "detail" in errorDetail
          ? String((errorDetail as { detail: unknown }).detail)
          : `Request failed with status ${res.status}`;
      throw new ApiError(res.status, message, errorDetail);
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : "Network error or server unreachable";
    throw new ApiError(0, message);
  }
}

export const api = {
  // Dashboard
  getDashboardSummary: () => request<DashboardSummary>("/api/dashboard/summary"),

  // Pull Requests
  getPullRequests: (params?: {
    page?: number;
    limit?: number;
    search?: string;
    status?: string;
    repo?: string;
    sort_by?: string;
    order?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", params.page.toString());
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.search) searchParams.set("search", params.search);
    if (params?.status) searchParams.set("status", params.status);
    if (params?.repo) searchParams.set("repo", params.repo);
    if (params?.sort_by) searchParams.set("sort_by", params.sort_by);
    if (params?.order) searchParams.set("order", params.order);
    const query = searchParams.toString();
    return request<PaginatedResponse<PullRequestItem>>(`/api/pull-requests${query ? `?${query}` : ""}`);
  },

  getPullRequestDetail: (deliveryId: string) =>
    request<PullRequestDetail>(`/api/pull-requests/${encodeURIComponent(deliveryId)}`),

  // Learnings
  getLearnings: (params?: {
    page?: number;
    limit?: number;
    search?: string;
    repo?: string;
    pr_number?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", params.page.toString());
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.search) searchParams.set("search", params.search);
    if (params?.repo) searchParams.set("repo", params.repo);
    if (params?.pr_number) searchParams.set("pr_number", params.pr_number.toString());
    const query = searchParams.toString();
    return request<PaginatedResponse<LearningItem>>(`/api/learnings${query ? `?${query}` : ""}`);
  },

  // Webhook Events
  getWebhookEvents: (params?: {
    page?: number;
    limit?: number;
    status?: string;
    search?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", params.page.toString());
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.status) searchParams.set("status", params.status);
    if (params?.search) searchParams.set("search", params.search);
    const query = searchParams.toString();
    return request<PaginatedResponse<WebhookEventItem>>(`/api/webhook-events${query ? `?${query}` : ""}`);
  },

  getWebhookEventDetail: (deliveryId: string) =>
    request<WebhookEventItem>(`/api/webhook-events/${encodeURIComponent(deliveryId)}`),

  // Email Deliveries
  getEmailDeliveries: (params?: {
    page?: number;
    limit?: number;
    status?: string;
    search?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", params.page.toString());
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.status) searchParams.set("status", params.status);
    if (params?.search) searchParams.set("search", params.search);
    const query = searchParams.toString();
    return request<PaginatedResponse<EmailDeliveryItem>>(`/api/email-deliveries${query ? `?${query}` : ""}`);
  },

  // System Health
  getSystemHealth: () => request<SystemHealthData>("/api/system/health"),

  // Settings
  getSettings: () => request<SettingsData>("/api/settings"),

  // ===================================================================
  // GitHub Contribution Explorer
  // ===================================================================

  searchExplorer: (q: string, type?: string) => {
    const params = new URLSearchParams({ q });
    if (type) params.set("type", type);
    return request<{
      query: string;
      mode: "user" | "repo";
      identifier1: string;
      identifier2: string | null;
      target: string;
    }>(`/api/explorer/search?${params.toString()}`);
  },

  getRecentSearches: (limit = 10) =>
    request<RecentSearchItem[]>(`/api/explorer/recent-searches?limit=${limit}`),

  getUserProfile: (username: string) =>
    request<ContributorProfile>(`/api/explorer/user/${encodeURIComponent(username)}`),

  getUserRepositories: (username: string, sort = "updated", page = 1, limit = 30) => {
    const params = new URLSearchParams({
      sort,
      page: page.toString(),
      limit: limit.toString(),
    });
    return request<RepositoryMetadata[]>(
      `/api/explorer/user/${encodeURIComponent(username)}/repos?${params.toString()}`
    );
  },

  getUserPullRequests: (
    username: string,
    state?: string,
    page = 1,
    limit = 30
  ) => {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    if (state && state !== "all") params.set("state", state);
    return request<{ total_count: number; items: ExplorerPRItem[] }>(
      `/api/explorer/user/${encodeURIComponent(username)}/prs?${params.toString()}`
    );
  },

  getRepositoryMetadata: (owner: string, repo: string) =>
    request<RepositoryMetadata>(`/api/explorer/repo/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`),

  getRepositoryPullRequests: (owner: string, repo: string, state = "all", page = 1, limit = 30) => {
    const params = new URLSearchParams({
      state,
      page: page.toString(),
      limit: limit.toString(),
    });
    return request<ExplorerPRItem[]>(
      `/api/explorer/repo/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/prs?${params.toString()}`
    );
  },

  getRepositoryContributors: (owner: string, repo: string, page = 1, limit = 30) => {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    return request<ContributorProfile[]>(
      `/api/explorer/repo/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contributors?${params.toString()}`
    );
  },

  getPRExploration: (owner: string, repo: string, prNumber: number) =>
    request<ExplorerPRDetail>(
      `/api/explorer/pr/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${prNumber}`
    ),

  analyzePRContribution: (owner: string, repo: string, prNumber: number) =>
    request<{
      status: string;
      repo: string;
      pr_number: number;
      reflection: ParsedReflection;
    }>(`/api/explorer/pr/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${prNumber}/analyze`, {
      method: "POST",
    }),

  saveContributionBookmark: (
    repo: string,
    prNumber: number,
    isSaved: boolean,
    prTitle?: string,
    prAuthor?: string,
    prUrl?: string
  ) =>
    request<{ repo: string; pr_number: number; is_saved: boolean }>(
      "/api/explorer/contributions/save",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo,
          pr_number: prNumber,
          is_saved: isSaved,
          pr_title: prTitle,
          pr_author: prAuthor,
          pr_url: prUrl,
        }),
      }
    ),

  getExplorerContributions: (params?: {
    page?: number;
    limit?: number;
    search?: string;
    repo?: string;
    author?: string;
    state?: string;
    analyzed_only?: boolean;
    saved_only?: boolean;
  }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set("page", params.page.toString());
    if (params?.limit) sp.set("limit", params.limit.toString());
    if (params?.search) sp.set("search", params.search);
    if (params?.repo) sp.set("repo", params.repo);
    if (params?.author) sp.set("author", params.author);
    if (params?.state) sp.set("state", params.state);
    if (params?.analyzed_only) sp.set("analyzed_only", "true");
    if (params?.saved_only) sp.set("saved_only", "true");
    const q = sp.toString();
    return request<PaginatedResponse<SavedContributionItem>>(
      `/api/explorer/contributions${q ? `?${q}` : ""}`
    );
  },

  // ===================================================================
  // Contributor Email Outreach
  // ===================================================================

  createOutreachDraft: (payload: OutreachDraftRequest) =>
    request<OutreachDraftResponse>("/api/outreach/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  sendOutreachEmail: (payload: OutreachSendRequest) =>
    request<{ status: string; message: string; outreach_id?: number }>("/api/outreach/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  getOutreachHistory: (params?: {
    page?: number;
    limit?: number;
    status?: string;
    search?: string;
  }) => {
    const sp = new URLSearchParams();
    if (params?.page) sp.set("page", params.page.toString());
    if (params?.limit) sp.set("limit", params.limit.toString());
    if (params?.status) sp.set("status", params.status);
    if (params?.search) sp.set("search", params.search);
    const q = sp.toString();
    return request<PaginatedResponse<OutreachRecordItem>>(`/api/outreach/history${q ? `?${q}` : ""}`);
  },
};


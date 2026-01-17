/**
 * Goals API
 */
import { api } from "./client";
import type {
  Goal,
  GoalDetail,
  GoalItemMatch,
  PaginatedResponse,
} from "@/types";

export interface CreateGoalRequest {
  name: string;
  description: string;
  priority_mode?: "STRICT" | "SOFT";
  priority_terms?: string[];
  negative_terms?: string[];
  batch_windows?: string[];
  digest_send_time?: string;
}

export interface SuggestKeywordsRequest {
  description: string;
  max_keywords?: number;
}

export interface SuggestKeywordsResponse {
  keywords: string[];
}

export interface GenerateGoalDraftRequest {
  intent: string;
  max_keywords?: number;
}

export interface GenerateGoalDraftResponse {
  name: string;
  description: string;
  keywords: string[];
}

export type UpdateGoalRequest = Partial<CreateGoalRequest>;

interface ApiWrapper<T> {
  code: number;
  message?: string;
  data: T;
}

export interface GoalStatusResponse {
  ok: boolean;
  status: "active" | "paused" | "archived";
}

export const goalsApi = {
  /**
   * 获取 Goal 列表
   */
  list: async (params?: { status?: string; page?: number; page_size?: number }): Promise<PaginatedResponse<Goal>> => {
    const response = await api.get<{
      code: number;
      data: Goal[];
      meta: { total: number; page: number; page_size: number; total_pages: number };
    }>("/goals", { params });
    return {
      items: response.data,
      total: response.meta.total,
      page: response.meta.page,
      page_size: response.meta.page_size,
      total_pages: response.meta.total_pages,
    };
  },

  /**
   * 获取单个 Goal 详情
   */
  get: async (id: string): Promise<GoalDetail> => {
    const response = await api.get<ApiWrapper<GoalDetail>>(`/goals/${id}`);
    return response.data;
  },

  /**
   * 创建 Goal
   */
  create: async (data: CreateGoalRequest): Promise<Goal> => {
    const response = await api.post<ApiWrapper<Goal>>("/goals", data);
    return response.data;
  },

  /**
   * 更新 Goal
   */
  update: async (id: string, data: UpdateGoalRequest): Promise<Goal> => {
    const response = await api.put<ApiWrapper<Goal>>(`/goals/${id}`, data);
    return response.data;
  },

  /**
   * 删除 Goal
   */
  delete: (id: string) => api.delete<void>(`/goals/${id}`),

  /**
   * 暂停 Goal
   */
  pause: (id: string) => api.post<GoalStatusResponse>(`/goals/${id}/pause`),

  /**
   * 恢复 Goal
   */
  resume: (id: string) => api.post<GoalStatusResponse>(`/goals/${id}/resume`),

  /**
   * 获取 Goal 的匹配 Items
   */
  getMatches: async (
    id: string,
    params?: { min_score?: number; page?: number; page_size?: number }
  ): Promise<PaginatedResponse<GoalItemMatch>> => {
    const response = await api.get<{
      code: number;
      data: GoalItemMatch[];
      meta: { total: number; page: number; page_size: number; total_pages: number };
    }>(`/goals/${id}/matches`, { params });
    return {
      items: response.data,
      total: response.meta.total,
      page: response.meta.page,
      page_size: response.meta.page_size,
      total_pages: response.meta.total_pages,
    };
  },

  /**
   * AI 生成建议关键词
   */
  suggestKeywords: async (data: SuggestKeywordsRequest): Promise<SuggestKeywordsResponse> => {
    const response = await api.post<ApiWrapper<SuggestKeywordsResponse>>(
      "/goals/suggest-keywords",
      data
    );
    return response.data;
  },

  /**
   * AI 生成目标草稿（名称/描述/关键词）
   */
  generateDraft: async (data: GenerateGoalDraftRequest): Promise<GenerateGoalDraftResponse> => {
    const response = await api.post<ApiWrapper<GenerateGoalDraftResponse>>(
      "/goals/generate-draft",
      data
    );
    return response.data;
  },
};


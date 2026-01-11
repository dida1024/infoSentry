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
  batch_windows?: string[];
  digest_send_time?: string;
}

export interface UpdateGoalRequest extends Partial<CreateGoalRequest> {}

interface ApiWrapper<T> {
  code: number;
  message?: string;
  data: T;
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
  pause: (id: string) => api.post<Goal>(`/goals/${id}/pause`),

  /**
   * 恢复 Goal
   */
  resume: (id: string) => api.post<Goal>(`/goals/${id}/resume`),

  /**
   * 获取 Goal 的匹配 Items
   */
  getMatches: (
    id: string,
    params?: { min_score?: number; page?: number; page_size?: number }
  ) =>
    api.get<PaginatedResponse<GoalItemMatch>>(`/goals/${id}/matches`, {
      params,
    }),
};


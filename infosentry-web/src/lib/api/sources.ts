/**
 * Sources API
 */
import { api } from "./client";
import type { PublicSource, Source, PaginatedResponse } from "@/types";

export interface CreateSourceRequest {
  type: "RSS";
  name: string;
  is_private?: boolean;
  config: {
    feed_url: string;
  };
  fetch_interval_sec?: number;
}

export interface UpdateSourceRequest {
  name?: string;
  fetch_interval_sec?: number;
  config?: Record<string, unknown>;
}

interface ApiWrapper<T> {
  code: number;
  message?: string;
  data: T;
}

export const sourcesApi = {
  /**
   * 获取 Source 列表
   */
  list: async (params?: {
    type?: string;
    enabled?: boolean;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Source>> => {
    const response = await api.get<{
      code: number;
      data: Source[];
      meta: { total: number; page: number; page_size: number; total_pages: number };
    }>("/sources", { params });
    return {
      items: response.data,
      total: response.meta.total,
      page: response.meta.page,
      page_size: response.meta.page_size,
      total_pages: response.meta.total_pages,
    };
  },

  /**
   * 获取公共 Source 列表
   */
  listPublic: async (params?: {
    type?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<PublicSource>> => {
    const response = await api.get<{
      code: number;
      data: PublicSource[];
      meta: { total: number; page: number; page_size: number; total_pages: number };
    }>("/sources/public", { params });
    return {
      items: response.data,
      total: response.meta.total,
      page: response.meta.page,
      page_size: response.meta.page_size,
      total_pages: response.meta.total_pages,
    };
  },

  /**
   * 获取单个 Source
   */
  get: async (id: string): Promise<Source> => {
    const response = await api.get<ApiWrapper<Source>>(`/sources/${id}`);
    return response.data;
  },

  /**
   * 创建 Source (仅 RSS)
   */
  create: async (data: CreateSourceRequest): Promise<Source> => {
    const response = await api.post<ApiWrapper<Source>>("/sources", data);
    return response.data;
  },

  /**
   * 更新 Source
   */
  update: async (id: string, data: UpdateSourceRequest): Promise<Source> => {
    const response = await api.put<ApiWrapper<Source>>(`/sources/${id}`, data);
    return response.data;
  },

  /**
   * 删除 Source
   */
  delete: (id: string) => api.delete<void>(`/sources/${id}`),

  /**
   * 启用 Source
   */
  enable: async (id: string): Promise<Source> => {
    const response = await api.post<ApiWrapper<Source>>(`/sources/${id}/enable`);
    return response.data;
  },

  /**
   * 禁用 Source
   */
  disable: async (id: string): Promise<Source> => {
    const response = await api.post<ApiWrapper<Source>>(`/sources/${id}/disable`);
    return response.data;
  },

  /**
   * 订阅公共 Source
   */
  subscribe: async (id: string): Promise<Source> => {
    const response = await api.post<ApiWrapper<Source>>(
      `/sources/${id}/subscribe`
    );
    return response.data;
  },
};


import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  sourcesApi,
  type CreateSourceRequest,
  type UpdateSourceRequest,
} from "@/lib/api/sources";

/**
 * Sources 相关 React Query Hooks
 */

// Query Keys
export const sourceKeys = {
  all: ["sources"] as const,
  lists: () => [...sourceKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) =>
    [...sourceKeys.lists(), filters] as const,
  publicLists: () => [...sourceKeys.all, "public"] as const,
  publicList: (filters: Record<string, unknown>) =>
    [...sourceKeys.publicLists(), filters] as const,
  details: () => [...sourceKeys.all, "detail"] as const,
  detail: (id: string) => [...sourceKeys.details(), id] as const,
};

/**
 * 获取 Source 列表
 */
export function useSources(params?: {
  type?: string;
  enabled?: boolean;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: sourceKeys.list(params || {}),
    queryFn: () => sourcesApi.list(params),
  });
}

/**
 * 获取公共 Source 列表
 */
export function usePublicSources(
  params?: {
    type?: string;
    page?: number;
    page_size?: number;
  },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: sourceKeys.publicList(params || {}),
    queryFn: () => sourcesApi.listPublic(params),
    enabled: options?.enabled ?? true,
  });
}

/**
 * 获取单个 Source
 */
export function useSource(id: string) {
  return useQuery({
    queryKey: sourceKeys.detail(id),
    queryFn: () => sourcesApi.get(id),
    enabled: !!id,
  });
}

/**
 * 创建 Source
 */
export function useCreateSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateSourceRequest) => sourcesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
      queryClient.invalidateQueries({ queryKey: sourceKeys.publicLists() });
    },
  });
}

/**
 * 更新 Source
 */
export function useUpdateSource(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateSourceRequest) => sourcesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
      queryClient.invalidateQueries({ queryKey: sourceKeys.publicLists() });
    },
  });
}

/**
 * 删除 Source
 */
export function useDeleteSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => sourcesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
      queryClient.invalidateQueries({ queryKey: sourceKeys.publicLists() });
    },
  });
}

/**
 * 启用 Source
 */
export function useEnableSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => sourcesApi.enable(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
      queryClient.invalidateQueries({ queryKey: sourceKeys.publicLists() });
    },
  });
}

/**
 * 禁用 Source
 */
export function useDisableSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => sourcesApi.disable(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
      queryClient.invalidateQueries({ queryKey: sourceKeys.publicLists() });
    },
  });
}

/**
 * 订阅公共 Source
 */
export function useSubscribeSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => sourcesApi.subscribe(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sourceKeys.publicLists() });
      queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
    },
  });
}


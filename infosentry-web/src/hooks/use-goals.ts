import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { goalsApi, type CreateGoalRequest, type UpdateGoalRequest } from "@/lib/api/goals";

/**
 * Goals 相关 React Query Hooks
 */

// Query Keys
export const goalKeys = {
  all: ["goals"] as const,
  lists: () => [...goalKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) =>
    [...goalKeys.lists(), filters] as const,
  details: () => [...goalKeys.all, "detail"] as const,
  detail: (id: string) => [...goalKeys.details(), id] as const,
  matches: (id: string) => [...goalKeys.detail(id), "matches"] as const,
};

/**
 * 获取 Goal 列表
 */
export function useGoals(params?: {
  status?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: goalKeys.list(params || {}),
    queryFn: () => goalsApi.list(params),
  });
}

/**
 * 获取单个 Goal
 */
export function useGoal(id: string) {
  return useQuery({
    queryKey: goalKeys.detail(id),
    queryFn: () => goalsApi.get(id),
    enabled: !!id,
  });
}

/**
 * 获取 Goal 的匹配 Items
 */
export function useGoalMatches(
  id: string,
  params?: { min_score?: number; page?: number; page_size?: number }
) {
  return useQuery({
    queryKey: goalKeys.matches(id),
    queryFn: () => goalsApi.getMatches(id, params),
    enabled: !!id,
  });
}

/**
 * 创建 Goal
 */
export function useCreateGoal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateGoalRequest) => goalsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: goalKeys.lists() });
    },
  });
}

/**
 * 更新 Goal
 */
export function useUpdateGoal(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateGoalRequest) => goalsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: goalKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: goalKeys.lists() });
    },
  });
}

/**
 * 删除 Goal
 */
export function useDeleteGoal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => goalsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: goalKeys.lists() });
    },
  });
}

/**
 * 暂停 Goal
 */
export function usePauseGoal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => goalsApi.pause(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: goalKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: goalKeys.lists() });
    },
  });
}

/**
 * 恢复 Goal
 */
export function useResumeGoal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => goalsApi.resume(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: goalKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: goalKeys.lists() });
    },
  });
}


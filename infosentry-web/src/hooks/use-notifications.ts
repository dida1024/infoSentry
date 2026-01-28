import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {
  notificationsApi,
  type FeedbackRequest,
} from "@/lib/api/notifications";

/**
 * Notifications 相关 React Query Hooks
 */

// Query Keys
export const notificationKeys = {
  all: ["notifications"] as const,
  lists: () => [...notificationKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) =>
    [...notificationKeys.lists(), filters] as const,
  infinite: (filters: Record<string, unknown>) =>
    [...notificationKeys.all, "infinite", filters] as const,
  details: () => [...notificationKeys.all, "detail"] as const,
  detail: (id: string) => [...notificationKeys.details(), id] as const,
};

/**
 * 获取通知列表（普通分页）
 */
export function useNotifications(params?: {
  goal_id?: string;
  status?: string;
  cursor?: string;
  page_size?: number;
}) {
  return useQuery({
    queryKey: notificationKeys.list(params || {}),
    queryFn: () => notificationsApi.list(params),
  });
}

/**
 * 获取通知列表（无限滚动）
 */
export function useInfiniteNotifications(params?: {
  goal_id?: string;
  status?: string;
  page_size?: number;
}) {
  return useInfiniteQuery({
    queryKey: notificationKeys.infinite(params || {}),
    queryFn: ({ pageParam }) =>
      notificationsApi.list({ ...params, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.next_cursor : undefined,
  });
}

/**
 * 获取单个通知
 */
export function useNotification(id: string) {
  return useQuery({
    queryKey: notificationKeys.detail(id),
    queryFn: () => notificationsApi.get(id),
    enabled: !!id,
  });
}

/**
 * 标记为已读
 */
export function useMarkAsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => notificationsApi.markAsRead(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({
        queryKey: notificationKeys.detail(id),
      });
      queryClient.invalidateQueries({ queryKey: notificationKeys.lists() });
    },
  });
}

/**
 * 提交反馈
 */
export function useSubmitFeedback() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      itemId,
      data,
    }: {
      itemId: string;
      data: FeedbackRequest;
    }) => notificationsApi.submitFeedback(itemId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.lists() });
    },
  });
}


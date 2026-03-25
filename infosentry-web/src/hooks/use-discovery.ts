import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { discoveryApi } from "@/lib/api";

export const discoveryKeys = {
  all: ["discovery"] as const,
  lists: () => [...discoveryKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) =>
    [...discoveryKeys.lists(), filters] as const,
  details: () => [...discoveryKeys.all, "detail"] as const,
  detail: (id: string) => [...discoveryKeys.details(), id] as const,
};

export function useDiscoverySessions(params?: {
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: discoveryKeys.list(params || {}),
    queryFn: () => discoveryApi.listSessions(params),
  });
}

export function useDiscoverySession(
  sessionId: string | null,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: discoveryKeys.detail(sessionId ?? ""),
    queryFn: () => discoveryApi.getSession(sessionId ?? ""),
    enabled: Boolean(sessionId) && (options?.enabled ?? true),
  });
}

export function useCreateDiscoverySession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: discoveryApi.createSession,
    onSuccess: (session) => {
      queryClient.setQueryData(discoveryKeys.detail(session.id), session);
      queryClient.invalidateQueries({ queryKey: discoveryKeys.lists() });
    },
  });
}

export function useSendDiscoveryMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      sessionId,
      content,
    }: {
      sessionId: string;
      content: string;
    }) => discoveryApi.sendMessage(sessionId, { content }),
    onSuccess: (session) => {
      queryClient.setQueryData(discoveryKeys.detail(session.id), session);
      queryClient.invalidateQueries({ queryKey: discoveryKeys.lists() });
    },
  });
}

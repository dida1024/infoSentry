"use client";

import { useMemo, useState } from "react";
import {
  Inbox,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  Ban,
  Check,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionHeader } from "@/components/layout";
import {
  Button,
  Card,
  CardContent,
  Badge,
  EmptyState,
  ListSkeleton,
  Alert,
} from "@/components/ui";
import {
  useInfiniteNotifications,
  useMarkAsRead,
  useSubmitFeedback,
} from "@/hooks/use-notifications";
import { useGoals } from "@/hooks/use-goals";
import { cn } from "@/lib/utils/cn";
import type { Notification } from "@/types";
import { useSearchParams } from "next/navigation";

const statusConfig = {
  PENDING: { label: "待读", variant: "info" as const },
  SENT: { label: "已发送", variant: "default" as const },
  READ: { label: "已读", variant: "success" as const },
  FAILED: { label: "发送失败", variant: "error" as const },
  SKIPPED: { label: "已跳过", variant: "warning" as const },
};

const decisionConfig = {
  IMMEDIATE: { label: "即时", variant: "error" as const },
  BATCH: { label: "批量", variant: "warning" as const },
  DIGEST: { label: "摘要", variant: "info" as const },
  IGNORE: { label: "忽略", variant: "default" as const },
};

function NotificationItem({
  notification,
  goalName,
}: {
  notification: Notification;
  goalName?: string;
}) {
  const markAsRead = useMarkAsRead();
  const submitFeedback = useSubmitFeedback();

  const item = notification.item;
  const goalId = notification.goal_id;

  const handleOpen = () => {
    if (notification.status !== "READ") {
      markAsRead.mutate(notification.id);
    }
    window.open(item.url, "_blank");
  };

  const handleFeedback = (type: "LIKE" | "DISLIKE", blockSource = false) => {
    submitFeedback.mutate(
      {
        itemId: item.id,
        data: {
          goal_id: goalId,
          feedback: type,
          block_source: blockSource,
        },
      },
      {
        onSuccess: () => {
          if (blockSource) {
            toast.success("已屏蔽此来源");
          } else {
            toast.success(type === "LIKE" ? "已标记为有帮助" : "已标记为不相关");
          }
        },
        onError: () => {
          toast.error("反馈提交失败，请重试");
        },
      }
    );
  };

  const reasons = notification.reason_json;
  const isUnread = notification.status !== "READ";

  return (
    <Card
      className={cn(
        "hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] transition-colors",
        isUnread && "border-l-2 border-l-[var(--color-accent)]"
      )}
    >
      <CardContent>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <button
                onClick={handleOpen}
                className="text-base font-semibold text-[var(--color-text-primary)] hover:text-[var(--color-accent)] text-left flex items-center gap-1"
              >
                {item.title}
                <ExternalLink className="h-3 w-3 flex-shrink-0" />
              </button>
              <Badge variant={decisionConfig[notification.decision].variant}>
                {decisionConfig[notification.decision].label}
              </Badge>
              <Badge variant={statusConfig[notification.status].variant}>
                {statusConfig[notification.status].label}
              </Badge>
            </div>

            {/* Snippet */}
            {item.snippet && (
              <p className="text-sm text-[var(--color-text-secondary)] line-clamp-2 mb-2">
                {item.snippet}
              </p>
            )}

            {/* Reason */}
            {reasons?.reason && (
              <p className="text-xs text-[var(--color-text-tertiary)] bg-[var(--color-bg-tertiary)] px-2 py-1 rounded mb-2">
                {reasons.reason}
              </p>
            )}

            {/* Meta */}
            <div className="flex items-center gap-4 text-xs text-[var(--color-text-tertiary)]">
              {goalName && (
                <span className="text-[var(--color-accent)] font-medium">
                  {goalName}
                </span>
              )}
              {item.source_name && <span>{item.source_name}</span>}
              <span>
                {new Date(notification.decided_at).toLocaleString("zh-CN")}
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-1">
            <button
              onClick={() => handleFeedback("LIKE")}
              disabled={submitFeedback.isPending}
              className="p-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-success)] hover:bg-[var(--color-success-bg)] rounded transition-colors"
              title="有帮助"
              aria-label="标记有帮助"
            >
              <ThumbsUp className="h-4 w-4" />
            </button>
            <button
              onClick={() => handleFeedback("DISLIKE")}
              disabled={submitFeedback.isPending}
              className="p-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-error)] hover:bg-[var(--color-error-bg)] rounded transition-colors"
              title="不相关"
              aria-label="标记不相关"
            >
              <ThumbsDown className="h-4 w-4" />
            </button>
            <button
              onClick={() => handleFeedback("DISLIKE", true)}
              disabled={submitFeedback.isPending}
              className="p-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] rounded transition-colors"
              title="屏蔽此来源"
              aria-label="屏蔽此来源"
            >
              <Ban className="h-4 w-4" />
            </button>
            {isUnread && (
              <button
                onClick={() => markAsRead.mutate(notification.id)}
                disabled={markAsRead.isPending}
                className="p-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)] rounded transition-colors"
                title="标记已读"
                aria-label="标记已读"
              >
                <Check className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function InboxPage() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q")?.trim().toLowerCase() ?? "";
  const [goalFilter, setGoalFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(
    undefined
  );

  const { data: goals } = useGoals();
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteNotifications({
    goal_id: goalFilter,
    status: statusFilter,
  });

  const goalsMap = useMemo(() => {
    return new Map((goals?.items ?? []).map((goal) => [goal.id, goal.name]));
  }, [goals?.items]);

  // 合并所有页面的数据
  const allItems = useMemo(() => {
    return data?.pages.flatMap((page) => page.items) ?? [];
  }, [data?.pages]);

  // 应用搜索过滤
  const items = useMemo(() => {
    if (!query) return allItems;
    return allItems.filter((notification) => {
      const goalName = goalsMap.get(notification.goal_id) ?? "";
      const haystack = [
        notification.item.title,
        notification.item.snippet ?? "",
        notification.item.source_name ?? "",
        goalName,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [allItems, goalsMap, query]);

  const statusOptions = [
    { value: undefined, label: "全部状态" },
    { value: "PENDING", label: "待读" },
    { value: "READ", label: "已读" },
    { value: "SENT", label: "已发送" },
  ];

  return (
    <PageShell className="space-y-6">
      <PageHeader title="收件箱" description="查看和反馈最新推送内容" />

      <section className="space-y-3">
        <SectionHeader
          title="筛选条件"
          description="聚焦与你目标相关的内容"
        />
        <div className="flex flex-col gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4 sm:flex-row sm:items-center sm:justify-between">
          <select
            value={goalFilter || ""}
            onChange={(e) => setGoalFilter(e.target.value || undefined)}
            className="w-full sm:w-56 px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-md bg-[var(--color-surface-2)] text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:border-[var(--color-accent)]"
          >
            <option value="">全部目标</option>
            {goals?.items?.map((goal) => (
              <option key={goal.id} value={goal.id}>
                {goal.name}
              </option>
            ))}
          </select>

          <div className="flex flex-wrap items-center gap-2">
            {statusOptions.map((option) => (
              <button
                key={option.value ?? "all"}
                onClick={() => setStatusFilter(option.value)}
                className={cn(
                  "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                  statusFilter === option.value
                    ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                    : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]"
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeader
          title="内容流"
          description={query ? `搜索结果：${query}` : "阅读并快速给出反馈"}
          actions={<Badge variant="default">{items.length} 条</Badge>}
        />
        {isLoading ? (
          <ListSkeleton count={5} />
        ) : error ? (
          <Alert variant="error">
            加载失败：{error.message}
            <button
              onClick={() => window.location.reload()}
              className="ml-2 font-medium hover:opacity-80"
            >
              重试
            </button>
          </Alert>
        ) : !items.length ? (
          <EmptyState
            icon={<Inbox className="h-12 w-12" />}
            title={query ? "未找到匹配内容" : "收件箱是空的"}
            description={
              query ? "试试更换关键词" : "当有新的信息推送时，会显示在这里"
            }
          />
        ) : (
          <div className="space-y-3">
            {items.map((notification) => {
              const goalName = goalsMap.get(notification.goal_id);
              return (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  goalName={goalName}
                />
              );
            })}

            {/* Load More Button */}
            {hasNextPage && !query && (
              <div className="flex justify-center pt-4">
                <Button
                  variant="secondary"
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                >
                  {isFetchingNextPage ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      加载中...
                    </>
                  ) : (
                    "加载更多"
                  )}
                </Button>
              </div>
            )}
          </div>
        )}
      </section>
    </PageShell>
  );
}


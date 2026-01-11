"use client";

import { useState } from "react";
import {
  Inbox,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  Ban,
  Check,
} from "lucide-react";
import { PageHeader } from "@/components/layout";
import {
  Card,
  CardContent,
  Badge,
  EmptyState,
  ListSkeleton,
  Alert,
} from "@/components/ui";
import {
  useNotifications,
  useMarkAsRead,
  useSubmitFeedback,
} from "@/hooks/use-notifications";
import { useGoals } from "@/hooks/use-goals";
import { cn } from "@/lib/utils/cn";
import type { Notification } from "@/types";

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
    submitFeedback.mutate({
      itemId: item.id,
      data: {
        goal_id: goalId,
        feedback: type,
        block_source: blockSource,
      },
    });
  };

  const reasons = notification.reason_json;
  const isUnread = notification.status !== "READ";

  return (
    <Card
      className={cn(
        "hover:border-gray-300 transition-colors",
        isUnread && "border-l-2 border-l-blue-500"
      )}
    >
      <CardContent>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <button
                onClick={handleOpen}
                className="text-base font-semibold text-gray-900 hover:text-blue-600 text-left flex items-center gap-1"
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
              <p className="text-sm text-gray-600 line-clamp-2 mb-2">
                {item.snippet}
              </p>
            )}

            {/* Reason */}
            {reasons?.reason && (
              <p className="text-xs text-gray-500 bg-gray-50 px-2 py-1 rounded mb-2">
                {reasons.reason}
              </p>
            )}

            {/* Meta */}
            <div className="flex items-center gap-4 text-xs text-gray-400">
              {goalName && (
                <span className="text-blue-600 font-medium">{goalName}</span>
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
              className="p-1.5 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
              title="有帮助"
            >
              <ThumbsUp className="h-4 w-4" />
            </button>
            <button
              onClick={() => handleFeedback("DISLIKE")}
              disabled={submitFeedback.isPending}
              className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
              title="不相关"
            >
              <ThumbsDown className="h-4 w-4" />
            </button>
            <button
              onClick={() => handleFeedback("DISLIKE", true)}
              disabled={submitFeedback.isPending}
              className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
              title="屏蔽此来源"
            >
              <Ban className="h-4 w-4" />
            </button>
            {isUnread && (
              <button
                onClick={() => markAsRead.mutate(notification.id)}
                disabled={markAsRead.isPending}
                className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                title="标记已读"
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
  const [goalFilter, setGoalFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(
    undefined
  );

  const { data: goals } = useGoals();
  const { data, isLoading, error } = useNotifications({
    goal_id: goalFilter,
    status: statusFilter,
  });

  const statusOptions = [
    { value: undefined, label: "全部状态" },
    { value: "PENDING", label: "待读" },
    { value: "READ", label: "已读" },
    { value: "SENT", label: "已发送" },
  ];

  return (
    <div>
      <PageHeader title="收件箱" description="查看和管理推送给您的信息" />

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        {/* Goal filter */}
        <select
          value={goalFilter || ""}
          onChange={(e) => setGoalFilter(e.target.value || undefined)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">全部目标</option>
          {goals?.items?.map((goal) => (
            <option key={goal.id} value={goal.id}>
              {goal.name}
            </option>
          ))}
        </select>

        {/* Status filter */}
        <div className="flex items-center gap-2">
          {statusOptions.map((option) => (
            <button
              key={option.value ?? "all"}
              onClick={() => setStatusFilter(option.value)}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                statusFilter === option.value
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-100"
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <ListSkeleton count={5} />
      ) : error ? (
        <Alert variant="error">
          加载失败：{error.message}
          <button
            onClick={() => window.location.reload()}
            className="ml-2 text-red-600 hover:text-red-700 font-medium"
          >
            重试
          </button>
        </Alert>
      ) : !data?.items?.length ? (
        <EmptyState
          icon={<Inbox className="h-12 w-12" />}
          title="收件箱是空的"
          description="当有新的信息推送时，会显示在这里"
        />
      ) : (
        <div className="space-y-3">
          {data.items.map((notification) => {
            const goal = goals?.items?.find(
              (g) => g.id === notification.goal_id
            );
            return (
              <NotificationItem
                key={notification.id}
                notification={notification}
                goalName={goal?.name}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}


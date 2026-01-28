"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Mail,
  Pencil,
  ThumbsUp,
  ThumbsDown,
  ExternalLink,
  Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionHeader } from "@/components/layout";
import {
  Button,
  Card,
  CardContent,
  Badge,
  ListSkeleton,
  EmptyState,
  Alert,
} from "@/components/ui";
import { useGoal, useGoalMatches, useDeleteGoal } from "@/hooks/use-goals";
import { useSubmitFeedback } from "@/hooks/use-notifications";
import { SendGoalEmailDialog } from "./send-goal-email-dialog";
import type { GoalItemMatch } from "@/types";

const statusConfig = {
  active: { label: "运行中", variant: "success" as const },
  paused: { label: "已暂停", variant: "warning" as const },
  archived: { label: "已归档", variant: "default" as const },
};

function MatchItem({ match, goalId }: { match: GoalItemMatch; goalId: string }) {
  const item = match.item;
  const submitFeedback = useSubmitFeedback();

  if (!item) return null;

  const handleFeedback = (type: "LIKE" | "DISLIKE") => {
    submitFeedback.mutate(
      {
        itemId: item.id,
        data: {
          goal_id: goalId,
          feedback: type,
        },
      },
      {
        onSuccess: () => {
          toast.success(type === "LIKE" ? "已标记为有帮助" : "已标记为不相关");
        },
        onError: () => {
          toast.error("反馈提交失败，请重试");
        },
      }
    );
  };

  const reasons = match.reasons_json as {
    reason?: string;
    evidence?: Array<{ type: string; value: string }>;
  };

  return (
    <div className="py-4 border-b border-[var(--color-border)] last:border-0">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-[var(--color-text-primary)] hover:text-[var(--color-accent)] flex items-center gap-1"
            >
              {item.title}
              <ExternalLink className="h-3 w-3" />
            </a>
            <Badge variant="info">{(match.match_score * 100).toFixed(0)}%</Badge>
          </div>

          {item.snippet && (
            <p className="text-sm text-[var(--color-text-secondary)] line-clamp-2 mb-2">
              {item.snippet}
            </p>
          )}

          {reasons?.reason && (
            <p className="text-xs text-[var(--color-text-tertiary)] bg-[var(--color-bg-tertiary)] px-2 py-1 rounded">
              匹配原因：{reasons.reason}
            </p>
          )}

          <div className="flex items-center gap-4 mt-2 text-xs text-[var(--color-text-tertiary)]">
            {item.source_name && <span>{item.source_name}</span>}
            {item.published_at && (
              <span>
                {new Date(item.published_at).toLocaleDateString("zh-CN")}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => handleFeedback("LIKE")}
            disabled={submitFeedback.isPending}
            className="p-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-success)] hover:bg-[var(--color-success-bg)] rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="喜欢"
            aria-label="喜欢"
          >
            <ThumbsUp className="h-4 w-4" />
          </button>
          <button
            onClick={() => handleFeedback("DISLIKE")}
            disabled={submitFeedback.isPending}
            className="p-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-error)] hover:bg-[var(--color-error-bg)] rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="不喜欢"
            aria-label="不喜欢"
          >
            <ThumbsDown className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function GoalDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { data: goal, isLoading: goalLoading, error: goalError } = useGoal(id);
  const { data: matches, isLoading: matchesLoading } = useGoalMatches(id);
  const deleteGoal = useDeleteGoal();
  const [showSendDialog, setShowSendDialog] = useState(false);

  const priorityTerms = goal?.priority_terms ?? [];
  const negativeTerms = goal?.negative_terms ?? [];

  const handleDelete = async () => {
    if (!confirm("确定要删除这个目标吗？此操作不可恢复。")) {
      return;
    }
    try {
      await deleteGoal.mutateAsync(id);
      toast.success("目标已删除");
      router.push("/goals");
    } catch {
      toast.error("删除失败，请重试");
    }
  };

  if (goalLoading) {
    return (
      <PageShell>
        <div className="mb-6">
          <Link
            href="/goals"
            className="inline-flex items-center gap-1 text-sm text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
          >
            <ArrowLeft className="h-4 w-4" />
            返回目标列表
          </Link>
        </div>
        <ListSkeleton count={1} />
      </PageShell>
    );
  }

  if (goalError || !goal) {
    return (
      <PageShell>
        <div className="mb-6">
          <Link
            href="/goals"
            className="inline-flex items-center gap-1 text-sm text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
          >
            <ArrowLeft className="h-4 w-4" />
            返回目标列表
          </Link>
        </div>
        <Alert variant="error">
          加载失败：目标不存在或已被删除
        </Alert>
      </PageShell>
    );
  }

  return (
    <PageShell className="space-y-6">
      <div className="mb-6">
        <Link
          href="/goals"
          className="inline-flex items-center gap-1 text-sm text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
        >
          <ArrowLeft className="h-4 w-4" />
          返回目标列表
        </Link>
      </div>

      <PageHeader
        title={goal.name}
        description={goal.description}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant={statusConfig[goal.status].variant}>
              {statusConfig[goal.status].label}
            </Badge>
            <Link href={`/goals/${id}/edit`}>
              <Button variant="secondary" size="sm">
                <Pencil className="h-4 w-4 mr-1" />
                编辑
              </Button>
            </Link>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowSendDialog(true)}
            >
              <Mail className="h-4 w-4 mr-1" />
              发送邮件
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleDelete}
              disabled={deleteGoal.isPending}
            >
              <Trash2 className="h-4 w-4 mr-1" />
              {deleteGoal.isPending ? "删除中..." : "删除"}
            </Button>
          </div>
        }
      />

      <section className="space-y-3">
        <SectionHeader title="目标概览" description="关键信息与关键词" />
        <Card>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-[var(--color-text-tertiary)]">
                  匹配模式
                </span>
                <p className="font-medium">
                  {goal.priority_mode === "STRICT" ? "严格" : "宽松"}
                </p>
              </div>
              <div>
                <span className="text-[var(--color-text-tertiary)]">
                  批量窗口
                </span>
                <p className="font-medium">
                  {goal.batch_windows?.length
                    ? goal.batch_windows.join("、")
                    : "—"}
                </p>
              </div>
              <div>
                <span className="text-[var(--color-text-tertiary)]">
                  创建时间
                </span>
                <p className="font-medium">
                  {new Date(goal.created_at).toLocaleDateString("zh-CN")}
                </p>
              </div>
              <div>
                <span className="text-[var(--color-text-tertiary)]">
                  更新时间
                </span>
                <p className="font-medium">
                  {new Date(goal.updated_at).toLocaleDateString("zh-CN")}
                </p>
              </div>
            </div>

            {(priorityTerms.length > 0 || negativeTerms.length > 0) && (
              <div className="border-t border-[var(--color-border)] pt-4">
                <span className="text-sm text-[var(--color-text-tertiary)] block mb-2">
                  关键词
                </span>
                <div className="flex flex-wrap gap-2">
                  {priorityTerms.map((term, idx) => (
                    <Badge key={`p:${term}:${idx}`} variant="default">
                      {term}
                    </Badge>
                  ))}
                  {negativeTerms.map((term, idx) => (
                    <Badge key={`n:${term}:${idx}`} variant="error">
                      - {term}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {showSendDialog && (
        <SendGoalEmailDialog
          goalId={id}
          onClose={() => setShowSendDialog(false)}
        />
      )}

      <section className="space-y-3">
        <SectionHeader
          title="高分匹配内容"
          description="最新相关内容与反馈"
        />
        <Card>
          <CardContent>
            {matchesLoading ? (
              <ListSkeleton count={3} />
            ) : !matches?.items?.length ? (
              <EmptyState
                title="暂无匹配内容"
                description="系统正在持续监测，有新匹配会自动出现"
              />
            ) : (
              <div className="divide-y divide-[var(--color-border)]">
                {matches.items.map((match) => (
                  <MatchItem key={match.id} match={match} goalId={id} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </PageShell>
  );
}

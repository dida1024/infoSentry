"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, Pencil, ThumbsUp, ThumbsDown, ExternalLink, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  Badge,
  ListSkeleton,
  EmptyState,
  Alert,
} from "@/components/ui";
import { useGoal, useGoalMatches, useDeleteGoal } from "@/hooks/use-goals";
import type { GoalItemMatch } from "@/types";

const statusConfig = {
  active: { label: "运行中", variant: "success" as const },
  paused: { label: "已暂停", variant: "warning" as const },
  archived: { label: "已归档", variant: "default" as const },
};

function MatchItem({ match }: { match: GoalItemMatch }) {
  const item = match.item;
  if (!item) return null;

  const reasons = match.reasons_json as {
    reason?: string;
    evidence?: Array<{ type: string; value: string }>;
  };

  return (
    <div className="py-4 border-b border-gray-100 last:border-0">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-gray-900 hover:text-blue-600 flex items-center gap-1"
            >
              {item.title}
              <ExternalLink className="h-3 w-3" />
            </a>
            <Badge variant="info">{(match.match_score * 100).toFixed(0)}%</Badge>
          </div>

          {item.snippet && (
            <p className="text-sm text-gray-600 line-clamp-2 mb-2">
              {item.snippet}
            </p>
          )}

          {reasons?.reason && (
            <p className="text-xs text-gray-500 bg-gray-50 px-2 py-1 rounded">
              匹配原因：{reasons.reason}
            </p>
          )}

          <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
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
            className="p-1.5 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
            title="喜欢"
          >
            <ThumbsUp className="h-4 w-4" />
          </button>
          <button
            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
            title="不喜欢"
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

  const priorityTerms = goal?.priority_terms ?? [];
  const negativeTerms = goal?.negative_terms ?? [];

  const handleDelete = async () => {
    if (!confirm("确定要删除这个目标吗？此操作不可恢复。")) {
      return;
    }
    try {
      await deleteGoal.mutateAsync(id);
      router.push("/goals");
    } catch {
      // Error handled by mutation
    }
  };

  if (goalLoading) {
    return (
      <div>
        <div className="mb-6">
          <Link
            href="/goals"
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4" />
            返回目标列表
          </Link>
        </div>
        <ListSkeleton count={1} />
      </div>
    );
  }

  if (goalError || !goal) {
    return (
      <div>
        <div className="mb-6">
          <Link
            href="/goals"
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4" />
            返回目标列表
          </Link>
        </div>
        <Alert variant="error">
          加载失败：目标不存在或已被删除
        </Alert>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <Link
          href="/goals"
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
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

      {/* Goal Info */}
      <Card className="mb-6">
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-500">匹配模式</span>
              <p className="font-medium">
                {goal.priority_mode === "STRICT" ? "严格" : "宽松"}
              </p>
            </div>
            <div>
              <span className="text-gray-500">批量窗口</span>
              <p className="font-medium">
                {goal.batch_windows?.length ? goal.batch_windows.join("、") : "—"}
              </p>
            </div>
            <div>
              <span className="text-gray-500">创建时间</span>
              <p className="font-medium">
                {new Date(goal.created_at).toLocaleDateString("zh-CN")}
              </p>
            </div>
            <div>
              <span className="text-gray-500">更新时间</span>
              <p className="font-medium">
                {new Date(goal.updated_at).toLocaleDateString("zh-CN")}
              </p>
            </div>
          </div>

          {(priorityTerms.length > 0 || negativeTerms.length > 0) && (
            <div className="mt-4 pt-4 border-t border-gray-100">
              <span className="text-sm text-gray-500 block mb-2">
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

      {/* Matches */}
      <Card>
        <CardHeader>
          <h2 className="text-base font-semibold text-gray-900">
            高分匹配内容
          </h2>
        </CardHeader>
        <CardContent>
          {matchesLoading ? (
            <ListSkeleton count={3} />
          ) : !matches?.items?.length ? (
            <EmptyState
              title="暂无匹配内容"
              description="系统正在持续监测，有新匹配会自动出现"
            />
          ) : (
            <div className="divide-y divide-gray-100">
              {matches.items.map((match) => (
                <MatchItem key={match.id} match={match} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}


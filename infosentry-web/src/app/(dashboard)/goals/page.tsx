"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Play, Pause, Target } from "lucide-react";
import { PageHeader, PageShell, SectionHeader } from "@/components/layout";
import {
  Button,
  Card,
  CardContent,
  Badge,
  EmptyState,
  ListSkeleton,
  Skeleton,
} from "@/components/ui";
import { useGoals, usePauseGoal, useResumeGoal } from "@/hooks/use-goals";
import type { Goal } from "@/types";
import { cn } from "@/lib/utils/cn";
import { useSearchParams } from "next/navigation";

const statusConfig = {
  active: { label: "运行中", variant: "success" as const },
  paused: { label: "已暂停", variant: "warning" as const },
  archived: { label: "已归档", variant: "default" as const },
};

function GoalCard({ goal }: { goal: Goal }) {
  const pauseGoal = usePauseGoal();
  const resumeGoal = useResumeGoal();

  const handleToggle = () => {
    if (goal.status === "active") {
      pauseGoal.mutate(goal.id);
    } else {
      resumeGoal.mutate(goal.id);
    }
  };

  const isToggling = pauseGoal.isPending || resumeGoal.isPending;

  return (
    <Card className="hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] transition-colors">
      <CardContent className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Link
              href={`/goals/${goal.id}`}
              className="text-base font-semibold text-[var(--color-text-primary)] hover:text-[var(--color-accent)] truncate"
            >
              {goal.name}
            </Link>
            <Badge variant={statusConfig[goal.status].variant}>
              {statusConfig[goal.status].label}
            </Badge>
          </div>
          <p className="text-sm text-[var(--color-text-secondary)] line-clamp-2">
            {goal.description || "暂无描述"}
          </p>
          <div className="flex items-center gap-4 mt-2 text-xs text-[var(--color-text-tertiary)]">
            <span>
              模式: {goal.priority_mode === "STRICT" ? "严格" : "宽松"}
            </span>
            <span>
              窗口: {goal.batch_windows?.length ? goal.batch_windows.join("、") : "—"}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleToggle}
            disabled={isToggling || goal.status === "archived"}
            title={goal.status === "active" ? "暂停" : "恢复"}
            aria-label={goal.status === "active" ? "暂停目标" : "恢复目标"}
          >
            {goal.status === "active" ? (
              <Pause className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </Button>
          <Link href={`/goals/${goal.id}`}>
            <Button variant="secondary" size="sm">
              查看
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

export default function GoalsPage() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q")?.trim().toLowerCase() ?? "";
  const [statusFilter, setStatusFilter] = useState<string | undefined>(
    undefined
  );
  const { data, isLoading, error } = useGoals({ status: statusFilter });
  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const filteredItems = useMemo(() => {
    if (!query) return items;
    return items.filter((goal) => {
      const haystack = `${goal.name} ${goal.description}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [items, query]);
  const hasSearch = query.length > 0;

  const summary = useMemo(() => {
    return items.reduce(
      (acc, goal) => {
        acc[goal.status] += 1;
        return acc;
      },
      { active: 0, paused: 0, archived: 0 }
    );
  }, [items]);

  const filterOptions = [
    { value: undefined, label: "全部" },
    { value: "active", label: "运行中" },
    { value: "paused", label: "已暂停" },
    { value: "archived", label: "已归档" },
  ];
  const activeFilterLabel =
    filterOptions.find((option) => option.value === statusFilter)?.label ??
    "全部";
  const isAllFilter = statusFilter === undefined;
  const emptyStateTitle = hasSearch
    ? "未找到匹配目标"
    : isAllFilter
      ? "还没有创建任何目标"
      : `暂无${activeFilterLabel}目标`;
  const emptyStateDescription = hasSearch
    ? "试试更换关键词"
    : isAllFilter
      ? "创建一个目标来开始追踪您感兴趣的信息"
      : "尝试切换其他状态";

  return (
    <PageShell className="space-y-8">
      <PageHeader
        title="目标"
        description="聚焦最重要的追踪意图与执行"
        actions={
          <Link href="/goals/new">
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              新建目标
            </Button>
          </Link>
        }
      />

      <section className="space-y-3">
        <SectionHeader
          title="目标概览"
          description="快速查看当前运行状态"
        />
        <div className="grid gap-3 sm:grid-cols-3">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <Card key={index}>
                <CardContent className="space-y-2">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-16" />
                </CardContent>
              </Card>
            ))
          ) : (
            [
              { label: "运行中", value: summary.active, tone: "success" as const },
              { label: "已暂停", value: summary.paused, tone: "warning" as const },
              { label: "已归档", value: summary.archived, tone: "default" as const },
            ].map((item) => (
              <Card key={item.label}>
                <CardContent className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-[var(--color-text-tertiary)]">
                      {item.label}
                    </p>
                    <p className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">
                      {item.value}
                    </p>
                  </div>
                  <Badge variant={item.tone}>{item.label}</Badge>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeader
          title="目标列表"
          description={hasSearch ? `搜索结果：${query}` : "保持清晰的节奏与反馈"}
          actions={
            <div className="flex items-center gap-2">
              <Badge variant="default">{filteredItems.length} 个</Badge>
            </div>
          }
        />

        <div className="flex flex-wrap items-center gap-2">
          {filterOptions.map((option) => (
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

        {isLoading ? (
          <ListSkeleton count={3} />
        ) : error ? (
          <div className="bg-[var(--color-error-bg)] border border-[var(--color-error-border)] rounded-md p-4 text-sm text-[var(--color-error)]">
            加载失败：{error.message}
            <button
              onClick={() => window.location.reload()}
              className="ml-2 font-medium hover:opacity-80"
            >
              重试
            </button>
          </div>
        ) : !filteredItems.length ? (
          <EmptyState
            icon={<Target className="h-12 w-12" />}
            title={emptyStateTitle}
            description={emptyStateDescription}
            action={
              isAllFilter ? (
                <Link href="/goals/new">
                  <Button>创建第一个目标</Button>
                </Link>
              ) : undefined
            }
          />
        ) : (
          <div className="space-y-3">
            {filteredItems.map((goal) => (
              <GoalCard key={goal.id} goal={goal} />
            ))}
          </div>
        )}
      </section>
    </PageShell>
  );
}

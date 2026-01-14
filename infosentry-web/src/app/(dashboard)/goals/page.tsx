"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Play, Pause, Target } from "lucide-react";
import { PageHeader } from "@/components/layout";
import {
  Button,
  Card,
  CardContent,
  Badge,
  EmptyState,
  ListSkeleton,
} from "@/components/ui";
import { useGoals, usePauseGoal, useResumeGoal } from "@/hooks/use-goals";
import type { Goal } from "@/types";
import { cn } from "@/lib/utils/cn";

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
    <Card className="hover:border-gray-300 transition-colors">
      <CardContent className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Link
              href={`/goals/${goal.id}`}
              className="text-base font-semibold text-gray-900 hover:text-blue-600 truncate"
            >
              {goal.name}
            </Link>
            <Badge variant={statusConfig[goal.status].variant}>
              {statusConfig[goal.status].label}
            </Badge>
          </div>
          <p className="text-sm text-gray-600 line-clamp-2">
            {goal.description || "暂无描述"}
          </p>
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
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
  const [statusFilter, setStatusFilter] = useState<string | undefined>(
    undefined
  );
  const { data, isLoading, error } = useGoals({ status: statusFilter });

  const filterOptions = [
    { value: undefined, label: "全部" },
    { value: "active", label: "运行中" },
    { value: "paused", label: "已暂停" },
    { value: "archived", label: "已归档" },
  ];

  return (
    <div>
      <PageHeader
        title="目标"
        description="管理您的信息追踪目标"
        actions={
          <Link href="/goals/new">
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              新建目标
            </Button>
          </Link>
        }
      />

      {/* Filter */}
      <div className="flex items-center gap-2 mb-6">
        {filterOptions.map((option) => (
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

      {/* Content */}
      {isLoading ? (
        <ListSkeleton count={3} />
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 text-sm text-red-800">
          加载失败：{error.message}
          <button
            onClick={() => window.location.reload()}
            className="ml-2 text-red-600 hover:text-red-700 font-medium"
          >
            重试
          </button>
        </div>
      ) : !data?.items?.length ? (
        <EmptyState
          icon={<Target className="h-12 w-12" />}
          title="还没有创建任何目标"
          description="创建一个目标来开始追踪您感兴趣的信息"
          action={
            <Link href="/goals/new">
              <Button>创建第一个目标</Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {data.items.map((goal) => (
            <GoalCard key={goal.id} goal={goal} />
          ))}
        </div>
      )}
    </div>
  );
}


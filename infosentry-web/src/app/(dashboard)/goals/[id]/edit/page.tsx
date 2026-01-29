"use client";

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { PageHeader, PageShell } from "@/components/layout";
import {
  Button,
  Input,
  Textarea,
  Card,
  CardContent,
  CardHeader,
  CardFooter,
  Alert,
  ListSkeleton,
} from "@/components/ui";
import { useGoal, useUpdateGoal, goalKeys } from "@/hooks/use-goals";

const timeWindowRegex = /^([01]?\d|2[0-3]):[0-5]\d$/;

const parseBatchWindows = (value?: string) =>
  value
    ? value
        .split(/[,\n，]+/)
        .map((item) => item.trim())
        .filter(Boolean)
    : [];

const schema = z
  .object({
    name: z.string().min(1, "请输入目标名称").max(100, "名称不能超过 100 字符"),
    description: z
      .string()
      .min(1, "请输入目标描述")
      .max(2000, "描述不能超过 2000 字符"),
    priority_terms: z.string().optional(),
    priority_mode: z.enum(["STRICT", "SOFT"]),
    batch_enabled: z.boolean().default(true),
    batch_windows: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    const windows = parseBatchWindows(data.batch_windows);
    if (data.batch_enabled && windows.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "请至少设置 1 个批量窗口时间",
        path: ["batch_windows"],
      });
      return;
    }
    if (windows.length > 3) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "批量窗口最多 3 个",
        path: ["batch_windows"],
      });
      return;
    }
    if (windows.some((window) => !timeWindowRegex.test(window))) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "时间格式应为 HH:MM，例如 09:00",
        path: ["batch_windows"],
      });
    }
  });

type FormData = z.infer<typeof schema>;

export default function EditGoalPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: goal, isLoading, error } = useGoal(id);
  const updateGoal = useUpdateGoal(id);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const batchEnabled = watch("batch_enabled");

  useEffect(() => {
    if (goal) {
      const priorityLines = goal.priority_terms ?? [];
      const negativeLines = (goal.negative_terms ?? []).map((t) => `-${t}`);

      reset({
        name: goal.name,
        description: goal.description,
        priority_mode: goal.priority_mode,
        priority_terms: [...priorityLines, ...negativeLines].join("\n"),
        batch_enabled: goal.batch_enabled,
        batch_windows: goal.batch_windows?.join(", ") ?? "",
      });
    }
  }, [goal, reset]);

  const onSubmit = async (data: FormData) => {
    try {
      // 将多行字符串转换为数组（前缀 - 表示排除词）
      const lines =
        data.priority_terms
          ?.split("\n")
          .map((term) => term.trim())
          .filter(Boolean) ?? [];

      const priority_terms: string[] = [];
      const negative_terms: string[] = [];

      for (const line of lines) {
        if (line.startsWith("-")) {
          const t = line.slice(1).trim();
          if (t) negative_terms.push(t);
        } else {
          priority_terms.push(line);
        }
      }

      const windows = parseBatchWindows(data.batch_windows);
      await updateGoal.mutateAsync({
        name: data.name,
        description: data.description,
        priority_mode: data.priority_mode,
        priority_terms: priority_terms.length ? priority_terms : undefined,
        negative_terms: negative_terms.length ? negative_terms : undefined,
        batch_enabled: data.batch_enabled,
        batch_windows:
          data.batch_enabled && windows.length ? windows : undefined,
      });

      // 等待缓存刷新完成后再跳转
      await queryClient.invalidateQueries({ queryKey: goalKeys.detail(id) });
      await queryClient.invalidateQueries({ queryKey: goalKeys.lists() });

      router.push(`/goals/${id}`);
    } catch {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return (
      <PageShell>
        <div className="mb-6">
          <Link
            href={`/goals/${id}`}
            className="inline-flex items-center gap-1 text-sm text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
          >
            <ArrowLeft className="h-4 w-4" />
            返回目标详情
          </Link>
        </div>
        <ListSkeleton count={1} />
      </PageShell>
    );
  }

  if (error || !goal) {
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
        <Alert variant="error">加载失败：目标不存在或已被删除</Alert>
      </PageShell>
    );
  }

  return (
    <PageShell className="space-y-6">
      <div className="mb-6">
        <Link
          href={`/goals/${id}`}
          className="inline-flex items-center gap-1 text-sm text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
        >
          <ArrowLeft className="h-4 w-4" />
          返回目标详情
        </Link>
      </div>

      <PageHeader title="编辑目标" description={goal.name} />

      {updateGoal.isError && (
        <Alert variant="error" className="mb-6">
          保存失败，请稍后重试
        </Alert>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
              目标信息
            </h2>
            <p className="text-sm text-[var(--color-text-secondary)]">
              调整目标描述与关键词以优化匹配
            </p>
          </CardHeader>
          <CardContent className="space-y-6">
            <Input
              label="目标名称"
              placeholder="例如：AI 行业动态追踪"
              error={errors.name?.message}
              {...register("name")}
            />

            <Textarea
              label="目标描述"
              placeholder="详细描述您想追踪的信息内容"
              error={errors.description?.message}
              rows={4}
              {...register("description")}
            />

            <Textarea
              label="优先关键词（可选）"
              placeholder="每行一个关键词，前缀 - 表示排除词"
              hint="例如：OpenAI、Claude、-广告"
              rows={4}
              {...register("priority_terms")}
            />

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-[var(--color-text-secondary)]">
                匹配模式
              </label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    value="SOFT"
                    className="h-4 w-4 text-[var(--color-accent)] border-[var(--color-border)]"
                    {...register("priority_mode")}
                  />
                  <span className="text-sm text-[var(--color-text-secondary)]">
                    宽松
                  </span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    value="STRICT"
                    className="h-4 w-4 text-[var(--color-accent)] border-[var(--color-border)]"
                    {...register("priority_mode")}
                  />
                  <span className="text-sm text-[var(--color-text-secondary)]">
                    严格
                  </span>
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-[var(--color-text-secondary)]">
                  批量推送
                </label>
                <label className="inline-flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                  <input
                    type="checkbox"
                    className="h-4 w-4 text-[var(--color-accent)] border-[var(--color-border)]"
                    {...register("batch_enabled")}
                  />
                  启用按窗口时间发送
                </label>
                <p className="text-xs text-[var(--color-text-tertiary)]">
                  关闭后将不按窗口时间发送批量邮件
                </p>
              </div>

              <Input
                label="批量窗口（最多 3 个）"
                placeholder="例如：12:30, 18:30"
                hint="用逗号或换行分隔（HH:MM）"
                error={errors.batch_windows?.message}
                disabled={!batchEnabled}
                {...register("batch_windows")}
              />
            </div>
          </CardContent>

          <CardFooter className="flex justify-end gap-3">
            <Link href={`/goals/${id}`}>
              <Button variant="secondary" type="button">
                取消
              </Button>
            </Link>
            <Button type="submit" isLoading={isSubmitting}>
              保存修改
            </Button>
          </CardFooter>
        </Card>
      </form>
    </PageShell>
  );
}

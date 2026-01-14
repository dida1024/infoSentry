"use client";

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout";
import {
  Button,
  Input,
  Textarea,
  Card,
  CardContent,
  CardFooter,
  Alert,
  ListSkeleton,
} from "@/components/ui";
import { useGoal, useUpdateGoal, goalKeys } from "@/hooks/use-goals";

const schema = z.object({
  name: z.string().min(1, "请输入目标名称").max(100, "名称不能超过 100 字符"),
  description: z
    .string()
    .min(1, "请输入目标描述")
    .max(2000, "描述不能超过 2000 字符"),
  priority_terms: z.string().optional(),
  priority_mode: z.enum(["STRICT", "SOFT"]),
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
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  useEffect(() => {
    if (goal) {
      const priorityLines = goal.priority_terms ?? [];
      const negativeLines = (goal.negative_terms ?? []).map((t) => `-${t}`);

      reset({
        name: goal.name,
        description: goal.description,
        priority_mode: goal.priority_mode,
        priority_terms: [...priorityLines, ...negativeLines].join("\n"),
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

      await updateGoal.mutateAsync({
        name: data.name,
        description: data.description,
        priority_mode: data.priority_mode,
        priority_terms: priority_terms.length ? priority_terms : undefined,
        negative_terms: negative_terms.length ? negative_terms : undefined,
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
      <div>
        <div className="mb-6">
          <Link
            href={`/goals/${id}`}
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4" />
            返回目标详情
          </Link>
        </div>
        <ListSkeleton count={1} />
      </div>
    );
  }

  if (error || !goal) {
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
        <Alert variant="error">加载失败：目标不存在或已被删除</Alert>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <Link
          href={`/goals/${id}`}
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
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

      <form onSubmit={handleSubmit(onSubmit)}>
        <Card>
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
              <label className="block text-sm font-medium text-gray-700">
                匹配模式
              </label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    value="SOFT"
                    className="h-4 w-4 text-blue-600"
                    {...register("priority_mode")}
                  />
                  <span className="text-sm text-gray-700">宽松</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    value="STRICT"
                    className="h-4 w-4 text-blue-600"
                    {...register("priority_mode")}
                  />
                  <span className="text-sm text-gray-700">严格</span>
                </label>
              </div>
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
    </div>
  );
}


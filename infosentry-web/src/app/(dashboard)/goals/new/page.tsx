"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/layout";
import {
  Button,
  Input,
  Textarea,
  Card,
  CardContent,
  CardFooter,
  Alert,
} from "@/components/ui";
import { useCreateGoal } from "@/hooks/use-goals";

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

export default function NewGoalPage() {
  const router = useRouter();
  const createGoal = useCreateGoal();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      priority_mode: "SOFT",
    },
  });

  const onSubmit = async (data: FormData) => {
    try {
      // 将多行字符串转换为数组
      const priority_terms = data.priority_terms
        ?.split("\n")
        .map((term) => term.trim())
        .filter(Boolean);

      const goal = await createGoal.mutateAsync({
        name: data.name,
        description: data.description,
        priority_mode: data.priority_mode,
        priority_terms: priority_terms?.length ? priority_terms : undefined,
      });
      router.push(`/goals/${goal.id}`);
    } catch {
      // Error handled by mutation
    }
  };

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
        title="新建目标"
        description="创建一个新的信息追踪目标"
      />

      {createGoal.isError && (
        <Alert variant="error" className="mb-6">
          创建失败，请稍后重试
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
              placeholder="详细描述您想追踪的信息内容，这将帮助 AI 更准确地筛选相关信息"
              hint="详细描述有助于提高匹配精度"
              error={errors.description?.message}
              rows={4}
              {...register("description")}
            />

            <Textarea
              label="优先关键词（可选）"
              placeholder="每行一个关键词，例如：&#10;OpenAI&#10;Claude&#10;GPT-4"
              hint="包含这些关键词的信息将获得更高的匹配分数"
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
              <p className="text-xs text-gray-500">
                严格模式：必须包含关键词才会推送；宽松模式：语义相关即可
              </p>
            </div>
          </CardContent>

          <CardFooter className="flex justify-end gap-3">
            <Link href="/goals">
              <Button variant="secondary" type="button">
                取消
              </Button>
            </Link>
            <Button type="submit" isLoading={isSubmitting}>
              创建目标
            </Button>
          </CardFooter>
        </Card>
      </form>
    </div>
  );
}


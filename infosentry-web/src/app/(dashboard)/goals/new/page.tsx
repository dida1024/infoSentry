"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, Sparkles } from "lucide-react";
import Link from "next/link";
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
} from "@/components/ui";
import {
  useCreateGoal,
  useGenerateGoalDraft,
  useSuggestKeywords,
} from "@/hooks/use-goals";

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
  const suggestKeywords = useSuggestKeywords();
  const generateGoalDraft = useGenerateGoalDraft();
  const [aiIntent, setAiIntent] = useState("");

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      priority_mode: "SOFT",
    },
  });

  const description = watch("description");

  const handleGenerateDraft = async () => {
    if (generateGoalDraft.isPending) return;
    const intent = aiIntent.trim();
    if (intent.length < 3) return;

    try {
      const result = await generateGoalDraft.mutateAsync({
        intent,
        max_keywords: 5,
      });

      if (result.name) {
        setValue("name", result.name, { shouldDirty: true, shouldValidate: true });
      }
      if (result.description) {
        setValue("description", result.description, {
          shouldDirty: true,
          shouldValidate: true,
        });
      }
      if (result.keywords?.length) {
        setValue("priority_terms", result.keywords.join("\n"), {
          shouldDirty: true,
          shouldValidate: true,
        });
      }
    } catch {
      // Error handled by mutation
    }
  };

  const handleSuggestKeywords = async () => {
    if (!description || description.trim().length < 10) {
      return;
    }

    try {
      const result = await suggestKeywords.mutateAsync({
        description: description.trim(),
        max_keywords: 5,
      });

      if (result.keywords.length > 0) {
        setValue("priority_terms", result.keywords.join("\n"));
      }
    } catch {
      // Error handled by mutation
    }
  };

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

      const goal = await createGoal.mutateAsync({
        name: data.name,
        description: data.description,
        priority_mode: data.priority_mode,
        priority_terms: priority_terms.length ? priority_terms : undefined,
        negative_terms: negative_terms.length ? negative_terms : undefined,
      });
      router.push(`/goals/${goal.id}`);
    } catch {
      // Error handled by mutation
    }
  };

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
        title="新建目标"
        description="创建一个新的信息追踪目标"
      />

      {createGoal.isError && (
        <Alert variant="error" className="mb-6">
          创建失败，请稍后重试
        </Alert>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
              AI 辅助
            </h2>
            <p className="text-sm text-[var(--color-text-secondary)]">
              用一句话描述目标，让 AI 自动生成初稿
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="goal-intent"
                  className="block text-sm font-medium text-[var(--color-text-secondary)]"
                >
                  AI 帮写（可选）
                </label>
                <button
                  type="button"
                  onClick={handleGenerateDraft}
                  disabled={
                    !aiIntent ||
                    aiIntent.trim().length < 3 ||
                    generateGoalDraft.isPending
                  }
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-[var(--color-accent)] bg-[var(--color-accent-soft)] rounded-md hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title={
                    !aiIntent || aiIntent.trim().length < 3
                      ? "请先用一句话描述你想关注什么（至少3个字符）"
                      : "AI 生成目标名称/描述/关键词"
                  }
                >
                  <Sparkles className="h-3 w-3" />
                  {generateGoalDraft.isPending ? "生成中..." : "AI 生成"}
                </button>
              </div>
              <input
                id="goal-intent"
                value={aiIntent}
                onChange={(e) => setAiIntent(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleGenerateDraft();
                  }
                }}
                placeholder="用一句话告诉 AI 你想关注什么，例如：关注 AI 行业投融资、模型发布与监管政策"
                maxLength={300}
                className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-md bg-[var(--color-surface-1)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:border-[var(--color-accent)] transition-colors"
              />
              <p className="text-xs text-[var(--color-text-tertiary)]">
                生成后会自动填充目标名称、描述和关键词，你可以再手动微调
              </p>
              {generateGoalDraft.isError && (
                <p className="text-xs text-[var(--color-error)]">
                  AI 生成失败，请稍后重试
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
              目标信息
            </h2>
            <p className="text-sm text-[var(--color-text-secondary)]">
              描述清晰可显著提升匹配效果
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
              placeholder="详细描述您想追踪的信息内容，这将帮助 AI 更准确地筛选相关信息"
              hint="详细描述有助于提高匹配精度"
              error={errors.description?.message}
              rows={4}
              {...register("description")}
            />

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-[var(--color-text-secondary)]">
                  优先关键词（可选）
                </label>
                <button
                  type="button"
                  onClick={handleSuggestKeywords}
                  disabled={
                    !description ||
                    description.trim().length < 10 ||
                    suggestKeywords.isPending
                  }
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-[var(--color-accent)] bg-[var(--color-accent-soft)] rounded-md hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title={
                    !description || description.trim().length < 10
                      ? "请先填写目标描述（至少10个字符）"
                      : "AI 生成建议关键词"
                  }
                >
                  <Sparkles className="h-3 w-3" />
                  {suggestKeywords.isPending ? "生成中..." : "AI 生成"}
                </button>
              </div>
              <textarea
                placeholder="每行一个关键词（前缀 - 表示排除词），例如：&#10;OpenAI&#10;Claude&#10;-广告"
                rows={4}
                className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-md bg-[var(--color-surface-1)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:border-[var(--color-accent)] transition-colors resize-y min-h-[80px]"
                {...register("priority_terms")}
              />
              <p className="text-xs text-[var(--color-text-tertiary)]">
                包含这些关键词的信息将获得更高的匹配分数
              </p>
            </div>

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
              <p className="text-xs text-[var(--color-text-tertiary)]">
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
    </PageShell>
  );
}


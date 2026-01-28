"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import { useCreateSource } from "@/hooks/use-sources";

const schema = z.object({
  name: z.string().min(1, "请输入信息源名称").max(100, "名称不能超过 100 字符"),
  feed_url: z.string().url("请输入有效的 RSS 链接"),
  fetch_interval_min: z
    .number()
    .min(5, "抓取间隔不能小于 5 分钟")
    .max(1440, "抓取间隔不能超过 24 小时"),
  is_private: z.boolean(),
});

type FormData = z.infer<typeof schema>;

interface AddSourceDialogProps {
  onClose: () => void;
}

export function AddSourceDialog({ onClose }: AddSourceDialogProps) {
  const createSource = useCreateSource();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      fetch_interval_min: 30,
      is_private: false,
    },
  });

  const onSubmit = async (data: FormData) => {
    try {
      await createSource.mutateAsync({
        type: "RSS",
        name: data.name,
        is_private: data.is_private,
        config: { feed_url: data.feed_url },
        fetch_interval_sec: data.fetch_interval_min * 60,
      });
      onClose();
    } catch {
      // Error handled by mutation
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div className="relative bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-lg shadow-[var(--shadow-lg)] w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
            添加 RSS 信息源
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] rounded"
            aria-label="关闭"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="p-4 space-y-4">
            {createSource.isError && (
              <Alert variant="error">添加失败，请检查链接是否有效</Alert>
            )}

            <Input
              label="信息源名称"
              placeholder="例如：36氪快讯"
              error={errors.name?.message}
              {...register("name")}
            />

            <Input
              label="RSS 链接"
              type="url"
              placeholder="https://example.com/rss.xml"
              error={errors.feed_url?.message}
              {...register("feed_url")}
            />

            <Input
              label="抓取间隔（分钟）"
              type="number"
              min={5}
              max={1440}
              error={errors.fetch_interval_min?.message}
              hint="建议设置为 15-60 分钟"
              {...register("fetch_interval_min", { valueAsNumber: true })}
            />

            <div className="flex items-start gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
              <input
                id="is_private"
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
                {...register("is_private")}
              />
              <label
                htmlFor="is_private"
                className="text-sm text-[var(--color-text-primary)]"
              >
                私密信息源
                <p className="text-xs text-[var(--color-text-tertiary)]">
                  仅自己可见，其他人不可订阅
                </p>
              </label>
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 px-4 py-3 border-t border-[var(--color-border)] bg-[var(--color-surface-2)] rounded-b-lg">
            <Button variant="secondary" type="button" onClick={onClose}>
              取消
            </Button>
            <Button type="submit" isLoading={isSubmitting}>
              添加
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}


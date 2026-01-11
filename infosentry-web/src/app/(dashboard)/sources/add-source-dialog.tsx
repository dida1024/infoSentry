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
    },
  });

  const onSubmit = async (data: FormData) => {
    try {
      await createSource.mutateAsync({
        type: "RSS",
        name: data.name,
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
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div className="relative bg-white rounded-lg shadow-lg w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">
            添加 RSS 信息源
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 rounded"
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
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 px-4 py-3 border-t border-gray-200 bg-gray-50 rounded-b-lg">
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


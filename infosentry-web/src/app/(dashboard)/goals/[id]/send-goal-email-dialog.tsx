"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X } from "lucide-react";
import { Alert, Button, Input } from "@/components/ui";
import { useSendGoalEmail } from "@/hooks/use-goals";
import type { SendGoalEmailResponse } from "@/lib/api/goals";

const schema = z.object({
  since: z.string().optional(),
  min_score: z.number().min(0).max(1),
  limit: z.number().int().min(1).max(50),
  include_sent: z.boolean(),
});

type FormData = z.infer<typeof schema>;

interface SendGoalEmailDialogProps {
  goalId: string;
  onClose: () => void;
}

function resolveErrorMessage(error: unknown): string {
  if (typeof error === "object" && error) {
    const responseMessage = (error as { response?: { data?: { message?: string } } })
      .response?.data?.message;
    if (responseMessage) return responseMessage;
    const maybeMessage = (error as { message?: string }).message;
    if (maybeMessage) return maybeMessage;
  }
  return "发送失败，请稍后再试";
}

export function SendGoalEmailDialog({ goalId, onClose }: SendGoalEmailDialogProps) {
  const sendEmail = useSendGoalEmail(goalId);
  const [preview, setPreview] = useState<SendGoalEmailResponse | null>(null);
  const [result, setResult] = useState<SendGoalEmailResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<"preview" | "send" | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      since: "",
      min_score: 0.6,
      limit: 20,
      include_sent: false,
    },
  });

  const handleAction = async (data: FormData, dryRun: boolean) => {
    setErrorMessage(null);
    setPreview(null);
    setResult(null);
    setPendingAction(dryRun ? "preview" : "send");

    let since: string | undefined;
    if (data.since?.trim()) {
      const parsed = new Date(data.since);
      if (Number.isNaN(parsed.getTime())) {
        setPendingAction(null);
        setErrorMessage("开始时间格式不正确");
        return;
      }
      since = parsed.toISOString();
    }

    try {
      const response = await sendEmail.mutateAsync({
        since,
        min_score: data.min_score,
        limit: data.limit,
        include_sent: data.include_sent,
        dry_run: dryRun,
      });
      if (dryRun) {
        setPreview(response);
      } else {
        setResult(response);
      }
    } catch (error) {
      setErrorMessage(resolveErrorMessage(error));
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="relative bg-white rounded-lg shadow-lg w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">发送目标邮件</h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 rounded"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form
          onSubmit={handleSubmit((data) => handleAction(data, false))}
        >
          <div className="p-4 space-y-4">
            {errorMessage && (
              <Alert variant="error">{errorMessage}</Alert>
            )}

            {result && (
              <Alert variant="success" title="发送完成">
                {result.message}（项目数：{result.items_count}，更新决策：{result.decisions_updated}）
              </Alert>
            )}

            {preview && !preview.preview && (
              <Alert variant="info">{preview.message}</Alert>
            )}

            {preview?.preview && (
              <div className="border border-gray-200 rounded-md p-3 text-sm bg-gray-50">
                <div className="font-medium text-gray-800 mb-2">预览内容</div>
                <div className="text-gray-700">
                  主题：{preview.preview.subject}
                </div>
                <div className="text-gray-700">
                  收件人：{preview.preview.to_email || "未配置"}
                </div>
                <div className="mt-2 text-gray-700">
                  {preview.preview.item_titles.length > 0 ? (
                    <ul className="list-disc pl-5 space-y-1">
                      {preview.preview.item_titles.map((title, index) => (
                        <li key={`${title}-${index}`}>{title}</li>
                      ))}
                    </ul>
                  ) : (
                    <span>暂无可发送的项目</span>
                  )}
                </div>
              </div>
            )}

            <Input
              label="开始时间"
              type="datetime-local"
              error={errors.since?.message}
              hint="不填则默认最近 24 小时"
              {...register("since")}
            />

            <Input
              label="最低匹配分数"
              type="number"
              min={0}
              max={1}
              step={0.05}
              error={errors.min_score?.message}
              hint="0~1，越高越严格"
              {...register("min_score", { valueAsNumber: true })}
            />

            <Input
              label="最大项目数"
              type="number"
              min={1}
              max={50}
              error={errors.limit?.message}
              hint="1~50"
              {...register("limit", { valueAsNumber: true })}
            />

            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                {...register("include_sent")}
              />
              包含已发送项目
            </label>
          </div>

          <div className="flex justify-between gap-3 px-4 py-3 border-t border-gray-200 bg-gray-50 rounded-b-lg">
            <Button variant="secondary" type="button" onClick={onClose}>
              关闭
            </Button>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                type="button"
                onClick={handleSubmit((data) => handleAction(data, true))}
                isLoading={pendingAction === "preview"}
              >
                预览
              </Button>
              <Button
                type="submit"
                isLoading={pendingAction === "send"}
              >
                发送
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button, Input, Alert } from "@/components/ui";
import { authApi } from "@/lib/api";

const schema = z.object({
  email: z.string().email("请输入有效的邮箱地址"),
});

type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    try {
      setStatus("idle");
      await authApi.requestMagicLink(data);
      setStatus("success");
      setMessage("登录链接已发送到您的邮箱，请检查收件箱");
    } catch {
      setStatus("error");
      setMessage("发送失败，请稍后重试");
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg-primary)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center h-12 w-12 bg-[var(--color-accent)] rounded-lg mb-4 shadow-[var(--shadow-sm)]">
            <span className="text-[var(--color-text-inverse)] text-xl font-semibold">
              iS
            </span>
          </div>
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
            infoSentry
          </h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            智能信息追踪与推送系统
          </p>
        </div>

        {/* Login Form */}
        <div className="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-lg p-6 shadow-[var(--shadow-sm)]">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-1">
            登录
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-6">
            输入邮箱地址，我们将发送一封包含登录链接的邮件
          </p>

          {status === "success" && (
            <Alert variant="success" className="mb-4">
              {message}
            </Alert>
          )}

          {status === "error" && (
            <Alert variant="error" className="mb-4">
              {message}
            </Alert>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input
              label="邮箱地址"
              type="email"
              placeholder="your@email.com"
              error={errors.email?.message}
              {...register("email")}
            />

            <Button
              type="submit"
              className="w-full"
              isLoading={isSubmitting}
              disabled={status === "success"}
            >
              发送登录链接
            </Button>
          </form>
        </div>

        <p className="text-xs text-[var(--color-text-tertiary)] text-center mt-6">
          登录即表示您同意我们的服务条款和隐私政策
        </p>
      </div>
    </div>
  );
}


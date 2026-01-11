"use client";

import { useEffect, useState, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { authApi } from "@/lib/api";
import { Alert } from "@/components/ui";

function CallbackContent() {
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const hasConsumed = useRef(false);

  useEffect(() => {
    // 防止 React StrictMode 重复执行
    if (hasConsumed.current) {
      return;
    }

    const token = searchParams.get("token");

    if (!token) {
      setError("无效的登录链接");
      return;
    }

    hasConsumed.current = true;

    const consumeToken = async () => {
      try {
        const response = await authApi.consumeMagicLink(token);
        login(response.access_token, response.user);
      } catch {
        setError("登录链接已过期或无效，请重新获取");
      }
    };

    consumeToken();
  }, [searchParams, login]);

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="w-full max-w-sm text-center">
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
          <a
            href="/login"
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            返回登录页面
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
        <p className="text-gray-500">正在验证登录...</p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-gray-500">加载中...</div>
        </div>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}


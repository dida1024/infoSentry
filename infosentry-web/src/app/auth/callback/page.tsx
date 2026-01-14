"use client";

import { useEffect, useState, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { authApi } from "@/lib/api";
import { Alert } from "@/components/ui";

function CallbackContent() {
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const hasConsumed = useRef(false);

  useEffect(() => {
    // 如果正在跳转中，不做任何操作
    if (isRedirecting) {
      return;
    }

    // 等待 auth 状态加载完成
    if (isLoading) {
      return;
    }

    // 如果用户已经登录，使用 window.location 彻底跳转（避免 React 路由循环）
    if (isAuthenticated) {
      setIsRedirecting(true);
      window.location.href = "/goals";
      return;
    }

    // 防止重复执行
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
        // 登录成功后直接跳转，不通过 React 路由
        localStorage.setItem("token", response.access_token);
        setIsRedirecting(true);
        window.location.href = "/goals";
      } catch (err: unknown) {
        // 从 Axios 错误中提取错误代码
        interface ApiErrorResponse {
          error?: { code?: string; message?: string };
        }
        const axiosError = err as { response?: { data?: ApiErrorResponse } };
        const errorCode = axiosError?.response?.data?.error?.code;

        if (errorCode === "MAGIC_LINK_ALREADY_USED") {
          setError("该登录链接已被使用，请重新获取");
        } else if (errorCode === "MAGIC_LINK_EXPIRED") {
          setError("登录链接已过期，请重新获取");
        } else {
          setError("登录链接无效，请重新获取");
        }
      }
    };

    consumeToken();
  }, [searchParams, isAuthenticated, isLoading, isRedirecting]);

  // 正在跳转中，显示加载状态
  if (isRedirecting) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-500">登录成功，正在跳转...</p>
        </div>
      </div>
    );
  }

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


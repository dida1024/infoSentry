"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { TopNav } from "./top-nav";
import { useAuth } from "@/contexts/auth-context";

interface AppLayoutProps {
  children: ReactNode;
}

/**
 * 应用主布局
 * 顶部导航 + 主内容区域
 */
export function AppLayout({ children }: AppLayoutProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  // 加载中显示骨架
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[var(--color-bg-primary)] flex items-center justify-center">
        <div className="text-sm text-[var(--color-text-secondary)]">
          加载中...
        </div>
      </div>
    );
  }

  // 未登录不渲染
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg-primary)] flex flex-col">
      <TopNav />
      <main id="main" className="flex-1">
        {children}
      </main>
    </div>
  );
}


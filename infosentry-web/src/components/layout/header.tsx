"use client";

import { type ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
}

/**
 * 页面头部组件
 * 包含标题、描述和操作按钮
 */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <header className="mb-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-text-primary)] tracking-tight">
            {title}
          </h1>
          {description && (
            <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
              {description}
            </p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}


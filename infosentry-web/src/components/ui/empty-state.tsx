import { type ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

/**
 * 空状态组件
 * 提供行动引导
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="text-center py-12">
      {icon && (
        <div className="flex justify-center mb-4 text-[var(--color-text-tertiary)]">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-medium text-[var(--color-text-primary)] mb-1">
        {title}
      </h3>
      {description && (
        <p className="text-sm text-[var(--color-text-secondary)] mb-4">
          {description}
        </p>
      )}
      {action}
    </div>
  );
}


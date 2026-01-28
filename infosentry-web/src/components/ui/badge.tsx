import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "error" | "info";
}

const styles = {
  default:
    "bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)] border border-[var(--color-border)]",
  success:
    "bg-[var(--color-success-bg)] text-[var(--color-success)] border border-[var(--color-success-border)]",
  warning:
    "bg-[var(--color-warning-bg)] text-[var(--color-warning)] border border-[var(--color-warning-border)]",
  error:
    "bg-[var(--color-error-bg)] text-[var(--color-error)] border border-[var(--color-error-border)]",
  info:
    "bg-[var(--color-info-bg)] text-[var(--color-info)] border border-[var(--color-info-border)]",
};

/**
 * 标签组件
 */
export function Badge({
  variant = "default",
  className,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
        styles[variant],
        className
      )}
      {...props}
    />
  );
}


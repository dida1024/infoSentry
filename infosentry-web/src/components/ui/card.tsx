import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

type CardProps = HTMLAttributes<HTMLDivElement>;

/**
 * 卡片组件
 * 简洁设计 - 无过度装饰
 */
export function Card({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-lg shadow-[var(--shadow-sm)]",
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "px-4 py-3 border-b border-[var(--color-border)]",
        className
      )}
      {...props}
    />
  );
}

export function CardContent({ className, ...props }: CardProps) {
  return <div className={cn("p-4", className)} {...props} />;
}

export function CardFooter({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "px-4 py-3 border-t border-[var(--color-border)] bg-[var(--color-surface-2)] rounded-b-lg",
        className
      )}
      {...props}
    />
  );
}


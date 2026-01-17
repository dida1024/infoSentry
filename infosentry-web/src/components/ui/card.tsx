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
      className={cn("bg-white border border-gray-200 rounded-lg", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: CardProps) {
  return (
    <div
      className={cn("px-4 py-3 border-b border-gray-200", className)}
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
        "px-4 py-3 border-t border-gray-200 bg-gray-50 rounded-b-lg",
        className
      )}
      {...props}
    />
  );
}


import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";
import { AlertCircle, CheckCircle, XCircle, Info } from "lucide-react";

interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "info" | "success" | "warning" | "error";
  title?: string;
}

const icons = {
  info: Info,
  success: CheckCircle,
  warning: AlertCircle,
  error: XCircle,
};

const styles = {
  info: "bg-[var(--color-info-bg)] border-[var(--color-info-border)] text-[var(--color-info)]",
  success:
    "bg-[var(--color-success-bg)] border-[var(--color-success-border)] text-[var(--color-success)]",
  warning:
    "bg-[var(--color-warning-bg)] border-[var(--color-warning-border)] text-[var(--color-warning)]",
  error:
    "bg-[var(--color-error-bg)] border-[var(--color-error-border)] text-[var(--color-error)]",
};

/**
 * 提示组件
 * 用于反馈信息、成功、警告、错误状态
 */
export function Alert({
  variant = "info",
  title,
  className,
  children,
  ...props
}: AlertProps) {
  const Icon = icons[variant];

  return (
    <div
      className={cn(
        "flex gap-3 p-4 border rounded-md text-sm",
        styles[variant],
        className
      )}
      role="alert"
      {...props}
    >
      <Icon className="h-5 w-5 flex-shrink-0" />
      <div>
        {title && <p className="font-medium mb-1">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  );
}


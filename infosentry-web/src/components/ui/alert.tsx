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
  info: "bg-blue-50 border-blue-200 text-blue-800",
  success: "bg-green-50 border-green-200 text-green-800",
  warning: "bg-yellow-50 border-yellow-200 text-yellow-800",
  error: "bg-red-50 border-red-200 text-red-800",
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


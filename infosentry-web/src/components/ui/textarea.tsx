import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

/**
 * 多行文本输入框组件
 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, error, hint, id, ...props }, ref) => {
    const inputId = id || props.name;

    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-[var(--color-text-secondary)]"
          >
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={inputId}
          className={cn(
            "w-full px-3 py-2 text-sm border rounded-md bg-[var(--color-surface-1)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] transition-colors resize-y min-h-[80px] focus-visible:outline-none focus-visible:ring-2 focus-visible:border-[var(--color-accent)] focus-visible:ring-[var(--color-accent)]",
            error
              ? "border-[var(--color-error-border)] focus-visible:border-[var(--color-error)] focus-visible:ring-[var(--color-error)]"
              : "border-[var(--color-border)]",
            className
          )}
          {...props}
        />
        {error && (
          <p className="text-xs text-[var(--color-error)]">{error}</p>
        )}
        {hint && !error && (
          <p className="text-xs text-[var(--color-text-tertiary)]">{hint}</p>
        )}
      </div>
    );
  }
);

Textarea.displayName = "Textarea";


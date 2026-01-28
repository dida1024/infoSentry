import { cn } from "@/lib/utils/cn";

interface SkeletonProps {
  className?: string;
}

/**
 * 骨架屏组件
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse bg-[var(--color-surface-3)] rounded",
        className
      )}
      aria-hidden="true"
    />
  );
}

/**
 * 卡片骨架屏
 */
export function CardSkeleton() {
  return (
    <div className="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-lg p-4 space-y-3 shadow-[var(--shadow-sm)]">
      <Skeleton className="h-5 w-3/4" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  );
}

/**
 * 列表骨架屏
 */
export function ListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}


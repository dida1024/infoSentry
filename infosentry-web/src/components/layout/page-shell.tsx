import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

type PageShellProps = HTMLAttributes<HTMLDivElement>;

export function PageShell({ className, ...props }: PageShellProps) {
  return (
    <div
      className={cn("mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8", className)}
      {...props}
    />
  );
}

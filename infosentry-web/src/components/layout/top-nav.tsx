"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Settings, LogOut, Search, Plus } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useAuth } from "@/contexts/auth-context";
import { Button } from "@/components/ui";

const navigation = [
  { name: "目标", href: "/goals" },
  { name: "信息源", href: "/sources" },
  { name: "收件箱", href: "/inbox" },
];

export function TopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { logout, user } = useAuth();
  const [query, setQuery] = useState("");

  useEffect(() => {
    setQuery(searchParams.get("q") ?? "");
  }, [searchParams]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextQuery = query.trim();
    const params = new URLSearchParams(searchParams);
    if (nextQuery) {
      params.set("q", nextQuery);
    } else {
      params.delete("q");
    }
    const next = params.toString();
    router.push(next ? `${pathname}?${next}` : pathname);
  };

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-surface-1)]/90 backdrop-blur">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-[var(--color-surface-1)] focus:px-3 focus:py-2 focus:text-sm focus:text-[var(--color-text-primary)]"
      >
        跳到主要内容
      </a>
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-6">
          <Link href="/goals" className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-[var(--color-accent)] shadow-[var(--shadow-sm)]">
              <span className="text-sm font-semibold text-[var(--color-text-inverse)]">
                iS
              </span>
            </div>
            <span className="hidden text-base font-semibold text-[var(--color-text-primary)] sm:inline">
              infoSentry
            </span>
          </Link>

          <nav className="hidden items-center gap-1 sm:flex">
            {navigation.map((item) => {
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                      : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]"
                  )}
                >
                  {item.name}
                </Link>
              );
            })}
          </nav>
        </div>

        <form
          onSubmit={handleSubmit}
          className="hidden flex-1 items-center md:flex"
        >
          <div className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索目标、信息源或收件箱"
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] py-2 pl-9 pr-3 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:border-[var(--color-accent)] focus-visible:ring-[var(--color-accent)]"
              aria-label="全局搜索"
            />
          </div>
        </form>

        <div className="flex items-center gap-2">
          <nav className="flex items-center gap-1 sm:hidden">
            {navigation.map((item) => {
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
                    isActive
                      ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                      : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]"
                  )}
                >
                  {item.name}
                </Link>
              );
            })}
          </nav>

          <Link href="/goals/new" className="sm:hidden">
            <button
              type="button"
              className="rounded-md px-2 py-2 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]"
              aria-label="新建目标"
            >
              <Plus className="h-4 w-4" />
            </button>
          </Link>

          <Link href="/goals/new" className="hidden sm:inline-flex">
            <Button size="sm">
              <Plus className="h-4 w-4" />
              新建目标
            </Button>
          </Link>

          <div className="hidden items-center gap-2 sm:flex">
            {user?.email && (
              <span className="text-xs text-[var(--color-text-tertiary)]">
                {user.email}
              </span>
            )}
            <Link
              href="/settings"
              className="rounded-md px-2 py-2 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]"
              aria-label="设置"
            >
              <Settings className="h-4 w-4" />
            </Link>
            <button
              onClick={logout}
              className="rounded-md px-2 py-2 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]"
              aria-label="退出登录"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Target, Rss, Inbox, Settings, LogOut } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useAuth } from "@/contexts/auth-context";

const navigation = [
  { name: "目标", href: "/goals", icon: Target },
  { name: "信息源", href: "/sources", icon: Rss },
  { name: "收件箱", href: "/inbox", icon: Inbox },
];

export function Sidebar() {
  const pathname = usePathname();
  const { logout, user } = useAuth();

  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-[var(--color-surface-1)] border-r border-[var(--color-border)] flex flex-col">
      {/* Logo */}
      <div className="h-16 flex items-center px-5 border-b border-[var(--color-border)]">
        <Link href="/goals" className="flex items-center gap-3">
          <div className="h-9 w-9 bg-[var(--color-accent)] rounded-md flex items-center justify-center shadow-[var(--shadow-sm)]">
            <span className="text-[var(--color-text-inverse)] text-sm font-semibold">
              iS
            </span>
          </div>
          <span className="font-semibold text-[var(--color-text-primary)] tracking-tight">
            infoSentry
          </span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3">
        <ul className="space-y-1">
          {navigation.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <li key={item.name}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md transition-colors",
                    isActive
                      ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                      : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]"
                  )}
                >
                  <item.icon className="h-5 w-5 flex-shrink-0" />
                  {item.name}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Bottom section */}
      <div className="border-t border-[var(--color-border)] py-4 px-3 space-y-1">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2 text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)] rounded-md transition-colors"
        >
          <Settings className="h-5 w-5 flex-shrink-0" />
          设置
        </Link>

        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)] rounded-md transition-colors"
        >
          <LogOut className="h-5 w-5 flex-shrink-0" />
          退出登录
        </button>

        {/* User info */}
        {user && (
          <div className="mt-4 px-3 py-2 bg-[var(--color-bg-tertiary)] rounded-md border border-[var(--color-border)]">
            <p className="text-xs text-[var(--color-text-tertiary)] truncate">
              {user.email}
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}


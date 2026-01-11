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
    <aside className="fixed inset-y-0 left-0 w-56 bg-white border-r border-gray-200 flex flex-col">
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-gray-200">
        <Link href="/goals" className="flex items-center gap-2">
          <div className="h-7 w-7 bg-blue-600 rounded flex items-center justify-center">
            <span className="text-white text-sm font-semibold">iS</span>
          </div>
          <span className="font-semibold text-gray-900">infoSentry</span>
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
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-700 hover:bg-gray-100"
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
      <div className="border-t border-gray-200 py-4 px-3 space-y-1">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
        >
          <Settings className="h-5 w-5 flex-shrink-0" />
          设置
        </Link>

        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
        >
          <LogOut className="h-5 w-5 flex-shrink-0" />
          退出登录
        </button>

        {/* User info */}
        {user && (
          <div className="mt-4 px-3 py-2 bg-gray-50 rounded-md">
            <p className="text-xs text-gray-500 truncate">{user.email}</p>
          </div>
        )}
      </div>
    </aside>
  );
}


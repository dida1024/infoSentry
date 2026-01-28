"use client";

import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import { PageHeader, PageShell } from "@/components/layout";
import { Button, Card, CardContent, CardHeader, Input } from "@/components/ui";
import { useAuth } from "@/contexts/auth-context";
import { useTheme } from "@/contexts/theme-context";
import { authApi } from "@/lib/api/auth";
import { cn } from "@/lib/utils/cn";

// 常用时区列表（按地区分组）
const COMMON_TIMEZONES = [
  { value: "Asia/Shanghai", label: "中国标准时间 (UTC+8)" },
  { value: "Asia/Hong_Kong", label: "香港 (UTC+8)" },
  { value: "Asia/Tokyo", label: "日本 (UTC+9)" },
  { value: "Asia/Singapore", label: "新加坡 (UTC+8)" },
  { value: "America/New_York", label: "美东时间 (UTC-5/-4)" },
  { value: "America/Los_Angeles", label: "美西时间 (UTC-8/-7)" },
  { value: "Europe/London", label: "伦敦 (UTC+0/+1)" },
  { value: "Europe/Paris", label: "巴黎 (UTC+1/+2)" },
  { value: "Australia/Sydney", label: "悉尼 (UTC+10/+11)" },
];

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const { theme, setTheme } = useTheme();

  const [displayName, setDisplayName] = useState("");
  const [timezone, setTimezone] = useState("Asia/Shanghai");
  const [isSaving, setIsSaving] = useState(false);

  // 初始化表单值
  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name || "");
      setTimezone(user.timezone || "Asia/Shanghai");
    }
  }, [user]);

  // 检查是否有未保存的更改
  const hasChanges = useMemo(() => {
    if (!user) return false;
    return (
      displayName !== (user.display_name || "") ||
      timezone !== (user.timezone || "Asia/Shanghai")
    );
  }, [user, displayName, timezone]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await authApi.updateProfile({
        display_name: displayName || undefined,
        timezone,
      });
      await refreshUser?.();
      toast.success("设置已保存");
    } catch {
      toast.error("保存失败，请重试");
    } finally {
      setIsSaving(false);
    }
  };

  const themeOptions = [
    { value: "dark" as const, label: "深色" },
    { value: "light" as const, label: "浅色" },
    { value: "system" as const, label: "跟随系统" },
  ];

  return (
    <PageShell className="space-y-6">
      <PageHeader title="设置" description="管理您的账户和偏好设置" />

      <div className="space-y-6">
        {/* Account */}
        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
              账户信息
            </h2>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-[var(--color-text-tertiary)] mb-1">
                  邮箱地址
                </label>
                <p className="text-sm font-medium text-[var(--color-text-primary)]">
                  {user?.email || "-"}
                </p>
              </div>

              <div>
                <label
                  htmlFor="displayName"
                  className="block text-sm text-[var(--color-text-tertiary)] mb-1"
                >
                  显示名称
                </label>
                <Input
                  id="displayName"
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="设置您的显示名称"
                  className="max-w-sm"
                />
              </div>

              <div>
                <label
                  htmlFor="timezone"
                  className="block text-sm text-[var(--color-text-tertiary)] mb-1"
                >
                  时区
                </label>
                <select
                  id="timezone"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full max-w-sm px-3 py-2 text-sm border border-[var(--color-border)] rounded-md bg-[var(--color-surface-2)] text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:border-[var(--color-accent)]"
                >
                  {COMMON_TIMEZONES.map((tz) => (
                    <option key={tz.value} value={tz.value}>
                      {tz.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">
                  用于摘要邮件和批量推送的发送时间
                </p>
              </div>

              <div>
                <label className="block text-sm text-[var(--color-text-tertiary)] mb-1">
                  账户状态
                </label>
                <p className="text-sm font-medium text-[var(--color-success)]">
                  {user?.is_active ? "正常" : "已禁用"}
                </p>
              </div>

              {hasChanges && (
                <div className="pt-2">
                  <Button
                    onClick={handleSave}
                    disabled={isSaving}
                    isLoading={isSaving}
                  >
                    保存更改
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Appearance */}
        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
              外观
            </h2>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-[var(--color-text-primary)]">
                  主题模式
                </p>
                <p className="text-xs text-[var(--color-text-tertiary)]">
                  默认暗色，支持跟随系统偏好
                </p>
              </div>
              <div className="inline-flex rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-1">
                {themeOptions.map((option) => {
                  const isActive = theme === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setTheme(option.value)}
                      aria-pressed={isActive}
                      className={cn(
                        "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                        isActive
                          ? "bg-[var(--color-surface-1)] text-[var(--color-text-primary)] shadow-[var(--shadow-sm)]"
                          : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
                      )}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Preferences */}
        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
              推送偏好
            </h2>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[var(--color-text-secondary)]">
              推送设置在每个目标中单独配置
            </p>
          </CardContent>
        </Card>

        {/* About */}
        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
              关于
            </h2>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-[var(--color-text-tertiary)]">版本</span>
                <span className="text-[var(--color-text-primary)]">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-tertiary)]">项目</span>
                <span className="text-[var(--color-text-primary)]">
                  infoSentry
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}

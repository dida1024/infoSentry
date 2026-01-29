"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Plus,
  Play,
  Pause,
  Rss,
  Trash2,
  AlertCircle,
  Search,
  MinusCircle,
} from "lucide-react";
import { PageHeader, PageShell } from "@/components/layout";
import {
  Button,
  Card,
  CardContent,
  CardFooter,
  Badge,
  EmptyState,
  Alert,
  CardSkeleton,
} from "@/components/ui";
import {
  useSources,
  useEnableSource,
  useDisableSource,
  useDeleteSource,
  usePublicSources,
  useSubscribeSource,
} from "@/hooks/use-sources";
import { AddSourceDialog } from "./add-source-dialog";
import type { PublicSource, Source } from "@/types";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils/cn";

const getSourceUrl = (config: Record<string, unknown>) => {
  const typed = config as {
    feed_url?: string;
    list_url?: string;
    base_url?: string;
  };
  return typed.feed_url ?? typed.list_url ?? typed.base_url ?? "";
};

const matchesQuery = (
  source: Source | PublicSource,
  normalizedQuery: string
) => {
  if (!normalizedQuery) {
    return true;
  }
  const url = getSourceUrl(source.config);
  return (
    source.name.toLowerCase().includes(normalizedQuery) ||
    url.toLowerCase().includes(normalizedQuery)
  );
};

function SourcesGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, index) => (
        <CardSkeleton key={index} />
      ))}
    </div>
  );
}

function SourceCard({ source }: { source: Source }) {
  const enableSource = useEnableSource();
  const disableSource = useDisableSource();
  const deleteSource = useDeleteSource();

  const handleToggle = () => {
    if (source.enabled) {
      disableSource.mutate(source.id);
    } else {
      enableSource.mutate(source.id);
    }
  };

  const handleDelete = () => {
    const message = source.is_private
      ? `确定要删除私密信息源 "${source.name}" 吗？`
      : `确定要取消订阅信息源 "${source.name}" 吗？`;
    if (confirm(message)) {
      deleteSource.mutate(source.id);
    }
  };

  const isToggling = enableSource.isPending || disableSource.isPending;
  const isDeleting = deleteSource.isPending;
  const sourceUrl = getSourceUrl(source.config);
  const lastFetchLabel = source.last_fetch_at
    ? new Date(source.last_fetch_at).toLocaleString("zh-CN")
    : "尚未抓取";

  return (
    <Card className="flex h-full flex-col transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)]">
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-[var(--color-accent-soft)] text-[var(--color-accent)]">
              <Rss className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">
                {source.name}
              </p>
              <p className="text-xs text-[var(--color-text-tertiary)] truncate">
                {sourceUrl || "暂无链接"}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Badge variant={source.enabled ? "success" : "default"}>
              {source.enabled ? "已启用" : "已禁用"}
            </Badge>
            {source.is_private ? (
              <Badge variant="warning">私密</Badge>
            ) : (
              <Badge variant="info">公共</Badge>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--color-text-tertiary)]">
          <span className="rounded bg-[var(--color-bg-tertiary)] px-2 py-1 text-[var(--color-text-secondary)]">
            {source.type}
          </span>
          <span className="rounded bg-[var(--color-bg-tertiary)] px-2 py-1">
            抓取间隔 {source.fetch_interval_sec / 60} 分钟
          </span>
          {source.error_streak > 0 && (
            <span className="inline-flex items-center rounded bg-[var(--color-error-bg)] px-2 py-1 text-[var(--color-error)] border border-[var(--color-error-border)]">
              <AlertCircle className="mr-1 h-3 w-3" />
              错误 {source.error_streak}
            </span>
          )}
        </div>
      </CardContent>

      <CardFooter className="flex items-center justify-between">
        <span className="text-xs text-[var(--color-text-tertiary)]">
          上次抓取: {lastFetchLabel}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleToggle}
            disabled={isToggling}
            title={source.enabled ? "禁用" : "启用"}
            aria-label={source.enabled ? "禁用信息源" : "启用信息源"}
          >
            {source.enabled ? (
              <Pause className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </Button>
          {source.is_private ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDelete}
              disabled={isDeleting}
              title="删除"
              className="text-[var(--color-error)] hover:text-[var(--color-error)] hover:bg-[var(--color-error-bg)]"
              aria-label="删除信息源"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleDelete}
              disabled={isDeleting}
              title="取消订阅"
              className="gap-1"
            >
              <MinusCircle className="h-4 w-4" />
              取消订阅
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}

function PublicSourceCard({ source }: { source: PublicSource }) {
  const subscribeSource = useSubscribeSource();
  const sourceUrl = getSourceUrl(source.config);
  const isSubscribing = subscribeSource.isPending;
  const lastFetchLabel = source.last_fetch_at
    ? new Date(source.last_fetch_at).toLocaleString("zh-CN")
    : "尚未抓取";

  const handleSubscribe = () => {
    if (!source.is_subscribed) {
      subscribeSource.mutate(source.id);
    }
  };

  return (
    <Card className="flex h-full flex-col transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)]">
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-[var(--color-accent-soft)] text-[var(--color-accent)]">
              <Rss className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[var(--color-text-primary)] truncate">
                {source.name}
              </p>
              <p className="text-xs text-[var(--color-text-tertiary)] truncate">
                {sourceUrl || "暂无链接"}
              </p>
            </div>
          </div>
          <Badge variant="info">公共</Badge>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--color-text-tertiary)]">
          <span className="rounded bg-[var(--color-bg-tertiary)] px-2 py-1 text-[var(--color-text-secondary)]">
            {source.type}
          </span>
          <span className="rounded bg-[var(--color-bg-tertiary)] px-2 py-1">
            抓取间隔 {source.fetch_interval_sec / 60} 分钟
          </span>
        </div>
      </CardContent>

      <CardFooter className="flex items-center justify-between">
        <span className="text-xs text-[var(--color-text-tertiary)]">
          上次抓取: {lastFetchLabel}
        </span>
        <Button
          variant={source.is_subscribed ? "secondary" : "primary"}
          size="sm"
          onClick={handleSubscribe}
          disabled={isSubscribing || source.is_subscribed}
          aria-label={source.is_subscribed ? "已添加信息源" : "添加信息源"}
        >
          {source.is_subscribed ? "已添加" : "添加"}
        </Button>
      </CardFooter>
    </Card>
  );
}

type TabType = "my" | "public";

export default function SourcesPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<TabType>("my");

  const mySources = useSources();
  const publicSources = usePublicSources();
  const normalizedQuery = searchQuery.trim().toLowerCase();

  const filteredMySources = useMemo(
    () =>
      (mySources.data?.items ?? []).filter((source) =>
        matchesQuery(source, normalizedQuery)
      ),
    [mySources.data?.items, normalizedQuery]
  );

  const filteredPublicSources = useMemo(
    () =>
      (publicSources.data?.items ?? []).filter((source) =>
        matchesQuery(source, normalizedQuery)
      ),
    [publicSources.data?.items, normalizedQuery]
  );

  const isSearching = normalizedQuery.length > 0;
  const myCount = filteredMySources.length;
  const publicCount = filteredPublicSources.length;

  useEffect(() => {
    setSearchQuery(searchParams.get("q") ?? "");
  }, [searchParams]);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    const nextQuery = value.trim();
    const params = new URLSearchParams(searchParams);
    if (nextQuery) {
      params.set("q", nextQuery);
    } else {
      params.delete("q");
    }
    const next = params.toString();
    router.replace(next ? `${pathname}?${next}` : pathname);
  };

  const tabs = [
    { id: "my" as const, label: "我的信息源", count: myCount },
    { id: "public" as const, label: "公共信息源", count: publicCount },
  ];

  const renderMySourcesContent = () => {
    if (mySources.isLoading) {
      return <SourcesGridSkeleton />;
    }
    if (mySources.error) {
      return (
        <Alert variant="error">
          加载失败：{mySources.error.message}
          <button
            onClick={() => window.location.reload()}
            className="ml-2 font-medium hover:opacity-80"
          >
            重试
          </button>
        </Alert>
      );
    }
    if (!mySources.data?.items?.length) {
      return (
        <EmptyState
          icon={<Rss className="h-12 w-12" />}
          title="还没有添加任何信息源"
          description="录入自己的信息源，或从公共信息源中添加"
          action={
            <div className="flex gap-3">
              <Button onClick={() => setShowAddDialog(true)}>
                <Plus className="h-4 w-4 mr-2" />
                录入信息源
              </Button>
              <Button variant="secondary" onClick={() => setActiveTab("public")}>
                浏览公共信息源
              </Button>
            </div>
          }
        />
      );
    }
    if (filteredMySources.length === 0) {
      return (
        <EmptyState
          icon={<Rss className="h-12 w-12" />}
          title="未找到匹配的信息源"
          description={isSearching ? "试试更换关键词" : "当前列表为空"}
        />
      );
    }
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filteredMySources.map((source) => (
          <SourceCard key={source.id} source={source} />
        ))}
      </div>
    );
  };

  const renderPublicSourcesContent = () => {
    if (publicSources.isLoading) {
      return <SourcesGridSkeleton />;
    }
    if (publicSources.error) {
      return (
        <Alert variant="error">
          加载失败：{publicSources.error.message}
          <button
            onClick={() => window.location.reload()}
            className="ml-2 font-medium hover:opacity-80"
          >
            重试
          </button>
        </Alert>
      );
    }
    if (!publicSources.data?.items?.length) {
      return (
        <EmptyState
          icon={<Rss className="h-12 w-12" />}
          title="暂无公共信息源"
          description="你可以录入新的信息源供自己使用"
          action={
            <Button onClick={() => setShowAddDialog(true)}>录入信息源</Button>
          }
        />
      );
    }
    if (filteredPublicSources.length === 0) {
      return (
        <EmptyState
          icon={<Rss className="h-12 w-12" />}
          title="未找到匹配的公共信息源"
          description={isSearching ? "试试更换关键词" : "暂无数据"}
        />
      );
    }
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filteredPublicSources.map((source) => (
          <PublicSourceCard key={source.id} source={source} />
        ))}
      </div>
    );
  };

  return (
    <PageShell className="space-y-6">
      <PageHeader
        title="信息源"
        description="管理你的信息订阅来源"
        actions={
          <Button onClick={() => setShowAddDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            录入信息源
          </Button>
        }
      />

      {/* 搜索 + Tab 导航 */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        {/* Tabs */}
        <div className="inline-flex rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "px-4 py-2 text-sm font-medium rounded-md transition-colors flex items-center gap-2",
                activeTab === tab.id
                  ? "bg-[var(--color-surface-1)] text-[var(--color-text-primary)] shadow-sm"
                  : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
              )}
            >
              {tab.label}
              <span
                className={cn(
                  "text-xs px-1.5 py-0.5 rounded-full",
                  activeTab === tab.id
                    ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
                    : "bg-[var(--color-bg-tertiary)] text-[var(--color-text-tertiary)]"
                )}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
          <input
            name="source_search"
            type="search"
            value={searchQuery}
            onChange={(event) => handleSearchChange(event.target.value)}
            placeholder="搜索信息源..."
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface-1)] py-2 pl-9 pr-3 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:border-[var(--color-accent)] focus-visible:ring-[var(--color-accent)]"
          />
        </div>
      </div>

      {/* Content */}
      <div>
        {activeTab === "my" ? renderMySourcesContent() : renderPublicSourcesContent()}
      </div>

      {showAddDialog && (
        <AddSourceDialog onClose={() => setShowAddDialog(false)} />
      )}
    </PageShell>
  );
}

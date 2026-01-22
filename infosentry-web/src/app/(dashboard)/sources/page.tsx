"use client";

import { useMemo, useState } from "react";
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
import { PageHeader } from "@/components/layout";
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
    <Card className="flex h-full flex-col border border-gray-200 transition hover:border-gray-300 hover:shadow-sm">
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-orange-50 text-orange-600">
              <Rss className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-gray-900 truncate">
                {source.name}
              </p>
              <p className="text-xs text-gray-500 truncate">
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

        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
          <span className="rounded bg-gray-100 px-2 py-1 text-gray-600">
            {source.type}
          </span>
          <span className="rounded bg-gray-100 px-2 py-1">
            抓取间隔 {source.fetch_interval_sec / 60} 分钟
          </span>
          {source.error_streak > 0 && (
            <span className="inline-flex items-center rounded bg-red-50 px-2 py-1 text-red-600">
              <AlertCircle className="mr-1 h-3 w-3" />
              错误 {source.error_streak}
            </span>
          )}
        </div>
      </CardContent>

      <CardFooter className="flex items-center justify-between">
        <span className="text-xs text-gray-500">上次抓取: {lastFetchLabel}</span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleToggle}
            disabled={isToggling}
            title={source.enabled ? "禁用" : "启用"}
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
              className="text-red-600 hover:text-red-700 hover:bg-red-50"
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
    <Card className="flex h-full flex-col border border-gray-200 transition hover:border-gray-300 hover:shadow-sm">
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-orange-50 text-orange-600">
              <Rss className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-gray-900 truncate">
                {source.name}
              </p>
              <p className="text-xs text-gray-500 truncate">
                {sourceUrl || "暂无链接"}
              </p>
            </div>
          </div>
          <Badge variant="info">公共</Badge>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
          <span className="rounded bg-gray-100 px-2 py-1 text-gray-600">
            {source.type}
          </span>
          <span className="rounded bg-gray-100 px-2 py-1">
            抓取间隔 {source.fetch_interval_sec / 60} 分钟
          </span>
        </div>
      </CardContent>

      <CardFooter className="flex items-center justify-between">
        <span className="text-xs text-gray-500">上次抓取: {lastFetchLabel}</span>
        <Button
          variant={source.is_subscribed ? "secondary" : "primary"}
          size="sm"
          onClick={handleSubscribe}
          disabled={isSubscribing || source.is_subscribed}
        >
          {source.is_subscribed ? "已添加" : "添加"}
        </Button>
      </CardFooter>
    </Card>
  );
}

export default function SourcesPage() {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
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

  return (
    <div>
      <PageHeader
        title="信息源"
        description="管理你的信息源，支持订阅公共源"
        actions={
          <Button onClick={() => setShowAddDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            录入信息源
          </Button>
        }
      />

      <div className="flex flex-col gap-3 mb-6 sm:flex-row sm:items-center sm:justify-end">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            name="source_search"
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="搜索信息源名称或链接"
            className="w-full rounded-md border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Content */}
      <div className="space-y-10">
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                我的信息源
              </h2>
              <p className="text-sm text-gray-500">
                你已订阅或录入的所有信息源
              </p>
            </div>
            <Badge variant="default">
              {filteredMySources.length} 个
            </Badge>
          </div>

          {mySources.isLoading ? (
            <SourcesGridSkeleton />
          ) : mySources.error ? (
            <Alert variant="error">
              加载失败：{mySources.error.message}
              <button
                onClick={() => window.location.reload()}
                className="ml-2 text-red-600 hover:text-red-700 font-medium"
              >
                重试
              </button>
            </Alert>
          ) : !mySources.data?.items?.length ? (
            <EmptyState
              icon={<Rss className="h-12 w-12" />}
              title="还没有添加任何信息源"
              description="录入或订阅公共信息源来开始追踪信息"
              action={
                <Button onClick={() => setShowAddDialog(true)}>
                  录入第一个信息源
                </Button>
              }
            />
          ) : filteredMySources.length === 0 ? (
            <EmptyState
              icon={<Rss className="h-12 w-12" />}
              title="未找到匹配的信息源"
              description={
                isSearching
                  ? "试试更换关键词，或清空搜索条件"
                  : "当前列表为空"
              }
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredMySources.map((source) => (
                <SourceCard key={source.id} source={source} />
              ))}
            </div>
          )}
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                公共信息源
              </h2>
              <p className="text-sm text-gray-500">
                所有人可订阅的公共信息源
              </p>
            </div>
            <Badge variant="default">
              {filteredPublicSources.length} 个
            </Badge>
          </div>

          {publicSources.isLoading ? (
            <SourcesGridSkeleton />
          ) : publicSources.error ? (
            <Alert variant="error">
              加载失败：{publicSources.error.message}
              <button
                onClick={() => window.location.reload()}
                className="ml-2 text-red-600 hover:text-red-700 font-medium"
              >
                重试
              </button>
            </Alert>
          ) : !publicSources.data?.items?.length ? (
            <EmptyState
              icon={<Rss className="h-12 w-12" />}
              title="暂无公共信息源"
              description="你可以录入新的信息源供自己使用"
              action={
                <Button onClick={() => setShowAddDialog(true)}>
                  录入信息源
                </Button>
              }
            />
          ) : filteredPublicSources.length === 0 ? (
            <EmptyState
              icon={<Rss className="h-12 w-12" />}
              title="未找到匹配的公共信息源"
              description={
                isSearching ? "试试更换关键词，或清空搜索条件" : "暂无数据"
              }
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredPublicSources.map((source) => (
                <PublicSourceCard key={source.id} source={source} />
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Add Dialog */}
      {showAddDialog && (
        <AddSourceDialog onClose={() => setShowAddDialog(false)} />
      )}
    </div>
  );
}


"use client";

import { useState } from "react";
import { Plus, Play, Pause, Rss, Trash2, AlertCircle } from "lucide-react";
import { PageHeader } from "@/components/layout";
import {
  Button,
  Card,
  CardContent,
  Badge,
  EmptyState,
  ListSkeleton,
  Alert,
} from "@/components/ui";
import {
  useSources,
  useEnableSource,
  useDisableSource,
  useDeleteSource,
} from "@/hooks/use-sources";
import { AddSourceDialog } from "./add-source-dialog";
import type { Source } from "@/types";

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
    if (confirm(`确定要删除信息源 "${source.name}" 吗？`)) {
      deleteSource.mutate(source.id);
    }
  };

  const isToggling = enableSource.isPending || disableSource.isPending;
  const isDeleting = deleteSource.isPending;
  const feedUrl = (source.config as { feed_url?: string })?.feed_url;

  return (
    <Card className="hover:border-gray-300 transition-colors">
      <CardContent className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Rss className="h-4 w-4 text-orange-500 flex-shrink-0" />
            <span className="text-base font-semibold text-gray-900 truncate">
              {source.name}
            </span>
            <Badge variant={source.enabled ? "success" : "default"}>
              {source.enabled ? "已启用" : "已禁用"}
            </Badge>
            {source.error_streak > 0 && (
              <Badge variant="error">
                <AlertCircle className="h-3 w-3 mr-1" />
                错误 {source.error_streak}
              </Badge>
            )}
          </div>

          {feedUrl && (
            <p className="text-sm text-gray-600 truncate mb-1">{feedUrl}</p>
          )}

          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            <span>抓取间隔: {source.fetch_interval_sec / 60} 分钟</span>
            {source.last_fetch_at && (
              <span>
                上次抓取:{" "}
                {new Date(source.last_fetch_at).toLocaleString("zh-CN")}
              </span>
            )}
          </div>
        </div>

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
        </div>
      </CardContent>
    </Card>
  );
}

export default function SourcesPage() {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const { data, isLoading, error } = useSources();

  return (
    <div>
      <PageHeader
        title="信息源"
        description="管理您的 RSS 订阅源"
        actions={
          <Button onClick={() => setShowAddDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            添加信息源
          </Button>
        }
      />

      {/* Content */}
      {isLoading ? (
        <ListSkeleton count={3} />
      ) : error ? (
        <Alert variant="error">
          加载失败：{error.message}
          <button
            onClick={() => window.location.reload()}
            className="ml-2 text-red-600 hover:text-red-700 font-medium"
          >
            重试
          </button>
        </Alert>
      ) : !data?.items?.length ? (
        <EmptyState
          icon={<Rss className="h-12 w-12" />}
          title="还没有添加任何信息源"
          description="添加 RSS 订阅源来开始追踪信息"
          action={
            <Button onClick={() => setShowAddDialog(true)}>
              添加第一个信息源
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {data.items.map((source) => (
            <SourceCard key={source.id} source={source} />
          ))}
        </div>
      )}

      {/* Add Dialog */}
      {showAddDialog && (
        <AddSourceDialog onClose={() => setShowAddDialog(false)} />
      )}
    </div>
  );
}


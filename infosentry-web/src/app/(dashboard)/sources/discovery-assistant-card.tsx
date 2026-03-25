"use client";

import { useEffect, useRef, useState } from "react";
import {
  Bot,
  CheckCircle2,
  Loader2,
  Radio,
  RefreshCcw,
  Send,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import {
  useCreateDiscoverySession,
  useDiscoverySession,
  useDiscoverySessions,
  useSendDiscoveryMessage,
  discoveryKeys,
} from "@/hooks/use-discovery";
import { sourceKeys } from "@/hooks/use-sources";
import { discoveryApi } from "@/lib/api";
import { cn } from "@/lib/utils/cn";
import type {
  DiscoveryCandidate,
  DiscoverySessionMessage,
  DiscoveryStreamEvent,
} from "@/types";
import { useQueryClient } from "@tanstack/react-query";
import { Alert, Badge, Button, Card, CardContent, Textarea } from "@/components/ui";

const STORAGE_KEY = "infosentry.discovery.activeSessionId";

type ActivityItem =
  | {
      kind: "tool_call";
      text: string;
    }
  | {
      kind: "tool_result";
      text: string;
    }
  | {
      kind: "system";
      text: string;
    };

const statusVariant: Record<
  string,
  "default" | "info" | "success" | "warning" | "error"
> = {
  active: "info",
  waiting_user: "warning",
  completed: "success",
  failed: "error",
  expired: "default",
  discovered: "default",
  validating: "info",
  valid: "success",
  invalid: "error",
  accepted: "success",
  rejected: "default",
};

const statusLabel: Record<string, string> = {
  active: "进行中",
  waiting_user: "等待确认",
  completed: "已完成",
  failed: "失败",
  expired: "已过期",
  discovered: "已发现",
  validating: "验证中",
  valid: "可添加",
  invalid: "不可用",
  accepted: "已添加",
  rejected: "已拒绝",
};

const roleLabel: Record<string, string> = {
  user: "你",
  agent: "助手",
  system: "系统",
};

function renderActivityTone(kind: ActivityItem["kind"]) {
  switch (kind) {
    case "tool_call":
      return "text-[var(--color-info)] bg-[var(--color-info-bg)] border-[var(--color-info-border)]";
    case "tool_result":
      return "text-[var(--color-text-secondary)] bg-[var(--color-surface-2)] border-[var(--color-border)]";
    case "system":
      return "text-[var(--color-warning)] bg-[var(--color-warning-bg)] border-[var(--color-warning-border)]";
  }
}

function CandidateCard({
  candidate,
  onConfirm,
  disabled,
}: {
  candidate: DiscoveryCandidate;
  onConfirm: (candidate: DiscoveryCandidate) => void;
  disabled: boolean;
}) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-[var(--color-text-primary)]">
            {candidate.name}
          </p>
          <p className="break-all text-xs text-[var(--color-text-tertiary)]">
            {candidate.url}
          </p>
        </div>
        <Badge variant={statusVariant[candidate.status] ?? "default"}>
          {statusLabel[candidate.status] ?? candidate.status}
        </Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--color-text-tertiary)]">
        <span className="rounded bg-[var(--color-bg-tertiary)] px-2 py-1">
          {candidate.source_type}
        </span>
        <span className="rounded bg-[var(--color-bg-tertiary)] px-2 py-1">
          发现方式: {candidate.discovered_via}
        </span>
        {candidate.source_id ? (
          <span className="rounded bg-[var(--color-success-bg)] px-2 py-1 text-[var(--color-success)]">
            Source ID: {candidate.source_id}
          </span>
        ) : null}
      </div>

      {candidate.validation_result ? (
        <div className="mt-3 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-2 text-xs text-[var(--color-text-secondary)]">
          {Object.entries(candidate.validation_result).map(([key, value]) => (
            <div key={key} className="flex items-start justify-between gap-3">
              <span className="text-[var(--color-text-tertiary)]">{key}</span>
              <span className="text-right text-[var(--color-text-primary)]">
                {typeof value === "object" ? JSON.stringify(value) : String(value)}
              </span>
            </div>
          ))}
        </div>
      ) : null}

      {candidate.status === "valid" ? (
        <div className="mt-4 flex justify-end">
          <Button
            size="sm"
            onClick={() => onConfirm(candidate)}
            disabled={disabled}
          >
            <CheckCircle2 className="h-4 w-4" />
            确认添加
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function DiscoveryAssistantCard() {
  const queryClient = useQueryClient();
  const streamAbortRef = useRef<AbortController | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [messageDraft, setMessageDraft] = useState("");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activity, setActivity] = useState<ActivityItem[]>([]);

  const createSession = useCreateDiscoverySession();
  const sendMessage = useSendDiscoveryMessage();
  const sessionsQuery = useDiscoverySessions({ page: 1, page_size: 10 });
  const sessionQuery = useDiscoverySession(sessionId);
  const session = sessionQuery.data;

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const storedSessionId = window.localStorage.getItem(STORAGE_KEY);
    if (storedSessionId) {
      setSessionId(storedSessionId);
      return;
    }
    const recoverableSession = sessionsQuery.data?.items.find(
      (item) => item.status === "active" || item.status === "waiting_user"
    );
    if (recoverableSession) {
      setSessionId(recoverableSession.id);
    }
  }, [sessionsQuery.data?.items]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (sessionId) {
      window.localStorage.setItem(STORAGE_KEY, sessionId);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, [sessionId]);

  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort();
    };
  }, []);

  const appendActivity = (event: DiscoveryStreamEvent) => {
    if (event.event === "tool_call") {
      setActivity((current) => [
        ...current,
        { kind: "tool_call", text: `调用工具 ${event.data.tool}` },
      ]);
      return;
    }
    if (event.event === "tool_result") {
      setActivity((current) => [
        ...current,
        { kind: "tool_result", text: event.data.summary || "工具返回结果" },
      ]);
      return;
    }
    if (event.event === "confirm_required" || event.event === "session_completed") {
      setActivity((current) => [
        ...current,
        { kind: "system", text: event.data.message },
      ]);
      return;
    }
    if (event.event === "error") {
      setActivity((current) => [
        ...current,
        { kind: "system", text: event.data.message },
      ]);
    }
  };

  const refreshSession = async (nextSessionId: string) => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: discoveryKeys.detail(nextSessionId),
      }),
      queryClient.invalidateQueries({
        queryKey: discoveryKeys.lists(),
      }),
    ]);
  };

  const runStream = async (nextSessionId: string) => {
    streamAbortRef.current?.abort();
    const controller = new AbortController();
    streamAbortRef.current = controller;
    setIsStreaming(true);
    setStreamError(null);

    try {
      await discoveryApi.streamSession(nextSessionId, {
        signal: controller.signal,
        onEvent: (event) => {
          appendActivity(event);
          if (event.event === "error") {
            setStreamError(event.data.message);
          }
        },
      });
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      const message =
        error instanceof Error ? error.message : "实时连接失败，请稍后重试";
      setStreamError(message);
      toast.error(message);
    } finally {
      setIsStreaming(false);
      await refreshSession(nextSessionId);
      const latest = queryClient.getQueryData<{
        status?: string;
      }>(discoveryKeys.detail(nextSessionId));
      if (latest?.status === "completed") {
        queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
        queryClient.invalidateQueries({ queryKey: sourceKeys.publicLists() });
        toast.success("信息源已成功添加到你的列表");
      }
    }
  };

  const handleCreateSession = async () => {
    const trimmed = query.trim();
    if (!trimmed) {
      toast.error("先描述一下你想找什么信息源");
      return;
    }

    setActivity([]);
    setStreamError(null);

    try {
      const created = await createSession.mutateAsync({ query: trimmed });
      setSessionId(created.id);
      setQuery("");
      await runStream(created.id);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "创建发现会话失败";
      setStreamError(message);
      toast.error(message);
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!sessionId) {
      return;
    }
    const trimmed = content.trim();
    if (!trimmed) {
      return;
    }

    try {
      await sendMessage.mutateAsync({ sessionId, content: trimmed });
      setMessageDraft("");
      await refreshSession(sessionId);
      await runStream(sessionId);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "发送消息失败";
      setStreamError(message);
      toast.error(message);
    }
  };

  const handleConfirmCandidate = async (candidate: DiscoveryCandidate) => {
    await handleSendMessage(`确认添加「${candidate.name}」这个信息源`);
  };

  const handleReset = () => {
    streamAbortRef.current?.abort();
    setSessionId(null);
    setQuery("");
    setMessageDraft("");
    setStreamError(null);
    setActivity([]);
  };

  const isBusy =
    isStreaming || createSession.isPending || sendMessage.isPending;

  const sessionStatus = session?.status ?? null;
  const sessionMessages = session?.messages ?? [];
  const sessionCandidates = session?.candidates ?? [];

  return (
    <Card className="overflow-hidden border-[var(--color-border-strong)]">
      <div className="grid gap-0 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="border-b border-[var(--color-border)] lg:border-b-0 lg:border-r">
          <div className="border-b border-[var(--color-border)] bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.16),transparent_40%),linear-gradient(135deg,var(--color-surface-1),var(--color-surface-2))] px-5 py-5">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-2 rounded-full border border-[var(--color-info-border)] bg-[var(--color-info-bg)] px-3 py-1 text-xs font-medium text-[var(--color-info)]">
                  <Sparkles className="h-3.5 w-3.5" />
                  智能发现信息源
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
                    用自然语言让系统帮你找 RSS、站点和可订阅来源
                  </h2>
                  <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
                    输入你想追踪的主题，系统会自动搜索、验证，并在添加前让你确认。
                  </p>
                </div>
              </div>
              {sessionStatus ? (
                <Badge variant={statusVariant[sessionStatus] ?? "default"}>
                  {statusLabel[sessionStatus] ?? sessionStatus}
                </Badge>
              ) : null}
            </div>

            {!sessionId ? (
              <div className="mt-5 space-y-3">
                <Textarea
                  label="想找什么信息源？"
                  placeholder="例如：帮我找 AI 创业、大模型和智能体相关的中文 RSS 或稳定新闻源"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="min-h-[108px]"
                />
                <div className="flex flex-wrap items-center gap-3">
                  <Button onClick={handleCreateSession} isLoading={isBusy}>
                    <Bot className="h-4 w-4" />
                    开始发现
                  </Button>
                  <span className="text-xs text-[var(--color-text-tertiary)]">
                    一次只能有一个进行中的发现会话
                  </span>
                </div>
              </div>
            ) : (
              <div className="mt-5 flex flex-wrap items-center gap-3 text-sm text-[var(--color-text-secondary)]">
                <div className="inline-flex items-center gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-2">
                  <Radio
                    className={cn(
                      "h-4 w-4",
                      isStreaming ? "animate-pulse text-[var(--color-info)]" : ""
                    )}
                  />
                  {isStreaming ? "正在实时处理" : "会话已就绪"}
                </div>
                <Button variant="secondary" size="sm" onClick={() => void runStream(sessionId)} disabled={isBusy}>
                  <RefreshCcw className="h-4 w-4" />
                  继续运行
                </Button>
                <Button variant="ghost" size="sm" onClick={handleReset} disabled={isBusy}>
                  开始新会话
                </Button>
              </div>
            )}
          </div>

          <CardContent className="space-y-4">
            {streamError ? (
              <Alert variant="error" title="发现流程出错">
                {streamError}
              </Alert>
            ) : null}

            {sessionMessages.length > 0 ? (
              <div className="space-y-3">
                {sessionMessages.map((message: DiscoverySessionMessage, index) => (
                  <div
                    key={`${message.timestamp}-${index}`}
                    className={cn(
                      "rounded-lg border px-4 py-3",
                      message.role === "user"
                        ? "border-[var(--color-info-border)] bg-[var(--color-info-bg)]"
                        : message.role === "agent"
                          ? "border-[var(--color-border)] bg-[var(--color-surface-2)]"
                          : "border-[var(--color-warning-border)] bg-[var(--color-warning-bg)]"
                    )}
                  >
                    <div className="mb-1 flex items-center justify-between gap-3">
                      <span className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
                        {roleLabel[message.role] ?? message.role}
                      </span>
                      <span className="text-xs text-[var(--color-text-tertiary)]">
                        {new Date(message.timestamp).toLocaleString("zh-CN")}
                      </span>
                    </div>
                    <p className="whitespace-pre-wrap text-sm text-[var(--color-text-primary)]">
                      {message.content}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-6 text-sm text-[var(--color-text-secondary)]">
                会话创建后，助手的进展、提示和确认请求会显示在这里。
              </div>
            )}

            {sessionId ? (
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
                <Textarea
                  label="继续和发现助手对话"
                  placeholder={
                    sessionStatus === "waiting_user"
                      ? "例如：确认添加第一个候选，或者换一个更稳定的源"
                      : "例如：优先找 RSS，不要 RSSHub 镜像"
                  }
                  value={messageDraft}
                  onChange={(event) => setMessageDraft(event.target.value)}
                  className="min-h-[90px]"
                />
                <div className="mt-3 flex justify-end">
                  <Button
                    onClick={() => void handleSendMessage(messageDraft)}
                    isLoading={sendMessage.isPending}
                    disabled={isBusy || !messageDraft.trim()}
                  >
                    <Send className="h-4 w-4" />
                    发送并继续
                  </Button>
                </div>
              </div>
            ) : null}
          </CardContent>
        </div>

        <div className="flex flex-col bg-[var(--color-surface-2)]">
          <div className="border-b border-[var(--color-border)] px-5 py-4">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
              候选源与实时活动
            </h3>
            <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">
              这里会显示验证通过的候选源，以及当前流式执行的关键步骤。
            </p>
          </div>

          <div className="flex-1 space-y-5 p-5">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-tertiary)]">
                  候选信息源
                </p>
                {sessionCandidates.length > 0 ? (
                  <Badge variant="default">{sessionCandidates.length}</Badge>
                ) : null}
              </div>
              {sessionCandidates.length > 0 ? (
                <div className="space-y-3">
                  {sessionCandidates.map((candidate) => (
                    <CandidateCard
                      key={candidate.id}
                      candidate={candidate}
                      onConfirm={handleConfirmCandidate}
                      disabled={isBusy}
                    />
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-[var(--color-border)] px-4 py-6 text-sm text-[var(--color-text-secondary)]">
                  还没有候选源。创建会话后，验证成功的结果会出现在这里。
                </div>
              )}
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-tertiary)]">
                实时活动
              </p>
              {isStreaming ? (
                <div className="inline-flex items-center gap-2 rounded-md border border-[var(--color-info-border)] bg-[var(--color-info-bg)] px-3 py-2 text-xs text-[var(--color-info)]">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  正在接收实时事件
                </div>
              ) : null}
              {activity.length > 0 ? (
                <div className="space-y-2">
                  {activity.map((item, index) => (
                    <div
                      key={`${item.kind}-${index}`}
                      className={cn(
                        "rounded-md border px-3 py-2 text-xs",
                        renderActivityTone(item.kind)
                      )}
                    >
                      {item.text}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-[var(--color-border)] px-4 py-6 text-sm text-[var(--color-text-secondary)]">
                  创建会话后，这里会显示工具调用、验证结果和完成信号。
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

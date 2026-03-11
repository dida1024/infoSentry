"use client";

import { useState } from "react";
import { PageHeader, PageShell } from "@/components/layout";
import { Button, Card, CardContent, CardHeader, Badge, Alert } from "@/components/ui";
import {
  useApiKeys,
  useCreateApiKey,
  useRevokeApiKey,
  useRotateApiKey,
} from "@/hooks/use-api-keys";
import { API_KEY_SCOPES } from "@/types/api-keys";
import type { ApiKey, CreateApiKeyRequest } from "@/types/api-keys";
import {
  Key,
  Plus,
  Copy,
  Check,
  Trash2,
  RefreshCw,
  X,
  Eye,
  EyeOff,
  Shield,
  BookOpen,
  Clock,
} from "lucide-react";

// ── Create Key Dialog ────────────────────────────────────────────────────────

function CreateKeyDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (rawKey: string) => void;
}) {
  const [name, setName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [expiresInDays, setExpiresInDays] = useState<string>("");
  const createKey = useCreateApiKey();

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope)
        ? prev.filter((s) => s !== scope)
        : [...prev, scope]
    );
  };

  const selectAllScopes = () => {
    setSelectedScopes(API_KEY_SCOPES.map((s) => s.value));
  };

  const clearAllScopes = () => {
    setSelectedScopes([]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || selectedScopes.length === 0) return;

    const data: CreateApiKeyRequest = {
      name: name.trim(),
      scopes: selectedScopes,
      expires_in_days: expiresInDays ? parseInt(expiresInDays, 10) : null,
    };

    try {
      const result = await createKey.mutateAsync(data);
      onCreated(result.raw_key);
    } catch {
      // Error handled by mutation state
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative bg-[var(--color-surface-1)] rounded-lg shadow-lg w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">创建 API Key</h2>
          <button
            onClick={onClose}
            className="p-1 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] rounded"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="p-4 space-y-4">
            {createKey.isError && (
              <Alert variant="error">
                创建失败：{(createKey.error as Error)?.message || "未知错误"}
              </Alert>
            )}

            <div>
              <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
                名称
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：My GPT Agent"
                className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg bg-[var(--color-surface-2)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:border-transparent"
                maxLength={100}
                required
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-[var(--color-text-secondary)]">
                  权限范围
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={selectAllScopes}
                    className="text-xs text-[var(--color-accent)] hover:opacity-80"
                  >
                    全选
                  </button>
                  <span className="text-xs text-[var(--color-text-tertiary)]">|</span>
                  <button
                    type="button"
                    onClick={clearAllScopes}
                    className="text-xs text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
                  >
                    清除
                  </button>
                </div>
              </div>
              <div className="space-y-1 border border-[var(--color-border)] rounded-lg p-3 max-h-48 overflow-y-auto">
                {API_KEY_SCOPES.map((scope) => (
                  <label
                    key={scope.value}
                    className="flex items-center gap-2 py-1 cursor-pointer hover:bg-[var(--color-surface-2)] rounded px-1"
                  >
                    <input
                      type="checkbox"
                      checked={selectedScopes.includes(scope.value)}
                      onChange={() => toggleScope(scope.value)}
                      className="h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-accent)] focus:ring-[var(--color-accent)]"
                    />
                    <span className="text-sm text-[var(--color-text-secondary)]">{scope.label}</span>
                  </label>
                ))}
              </div>
              {selectedScopes.length === 0 && (
                <p className="mt-1 text-xs text-[var(--color-error)]">请至少选择一个权限</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
                有效期（天）
              </label>
              <input
                type="number"
                value={expiresInDays}
                onChange={(e) => setExpiresInDays(e.target.value)}
                placeholder="留空表示永不过期"
                className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg bg-[var(--color-surface-2)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:border-transparent"
                min={1}
                max={3650}
              />
              <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">留空则使用系统默认设置</p>
            </div>
          </div>

          <div className="flex justify-end gap-3 px-4 py-3 border-t border-[var(--color-border)] bg-[var(--color-surface-2)] rounded-b-lg">
            <Button variant="secondary" type="button" onClick={onClose}>
              取消
            </Button>
            <Button
              type="submit"
              isLoading={createKey.isPending}
              disabled={!name.trim() || selectedScopes.length === 0}
            >
              创建
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Key Reveal Dialog ────────────────────────────────────────────────────────

function KeyRevealDialog({
  rawKey,
  onClose,
}: {
  rawKey: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [visible, setVisible] = useState(false);

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(rawKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" aria-hidden="true" />
      <div className="relative bg-[var(--color-surface-1)] rounded-lg shadow-lg w-full max-w-md mx-4">
        <div className="px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
            API Key 创建成功
          </h2>
        </div>

        <div className="p-4 space-y-4">
          <Alert variant="warning">
            请立即复制并安全保存此 Key。关闭此对话框后将无法再次查看。
          </Alert>

          <div className="relative">
            <div className="flex items-center gap-2 bg-[var(--color-surface-2)] rounded-lg p-3 font-mono text-sm break-all">
              <span className="flex-1 text-[var(--color-text-primary)]">
                {visible ? rawKey : rawKey.slice(0, 12) + "\u2022".repeat(30)}
              </span>
              <button
                type="button"
                onClick={() => setVisible(!visible)}
                className="p-1 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] shrink-0"
              >
                {visible ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          <Button
            onClick={copyToClipboard}
            className="w-full"
            variant={copied ? "secondary" : "primary"}
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 mr-2" />
                已复制
              </>
            ) : (
              <>
                <Copy className="h-4 w-4 mr-2" />
                复制 API Key
              </>
            )}
          </Button>
        </div>

        <div className="flex justify-end px-4 py-3 border-t border-[var(--color-border)] bg-[var(--color-surface-2)] rounded-b-lg">
          <Button variant="secondary" onClick={onClose}>
            我已保存，关闭
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── API Key Row ──────────────────────────────────────────────────────────────

function ApiKeyRow({ apiKey }: { apiKey: ApiKey }) {
  const revokeKey = useRevokeApiKey();
  const rotateKey = useRotateApiKey();
  const [showReveal, setShowReveal] = useState<string | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState(false);

  const handleRevoke = async () => {
    try {
      await revokeKey.mutateAsync(apiKey.id);
      setConfirmRevoke(false);
    } catch {
      // Error in mutation state
    }
  };

  const handleRotate = async () => {
    try {
      const result = await rotateKey.mutateAsync(apiKey.id);
      setShowReveal(result.raw_key);
    } catch {
      // Error in mutation state
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "\u2014";
    return new Date(dateStr).toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const isExpired =
    apiKey.expires_at && new Date(apiKey.expires_at) < new Date();

  return (
    <>
      <div className="flex items-start justify-between py-4 border-b border-[var(--color-border)] last:border-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Key className="h-4 w-4 text-[var(--color-text-tertiary)] shrink-0" />
            <span className="text-sm font-medium text-[var(--color-text-primary)] truncate">
              {apiKey.name}
            </span>
            {!apiKey.is_active && (
              <Badge variant="error">已撤销</Badge>
            )}
            {isExpired && apiKey.is_active && (
              <Badge variant="warning">已过期</Badge>
            )}
            {apiKey.is_active && !isExpired && (
              <Badge variant="success">有效</Badge>
            )}
          </div>
          <div className="mt-1 flex items-center gap-4 text-xs text-[var(--color-text-tertiary)]">
            <span className="font-mono">{apiKey.key_prefix}&bull;&bull;&bull;</span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              创建于 {formatDate(apiKey.created_at)}
            </span>
            {apiKey.last_used_at && (
              <span>最近使用 {formatDate(apiKey.last_used_at)}</span>
            )}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {apiKey.scopes.map((scope) => (
              <span
                key={scope}
                className="inline-flex text-[10px] font-medium bg-[var(--color-surface-2)] text-[var(--color-text-tertiary)] px-1.5 py-0.5 rounded"
              >
                {scope}
              </span>
            ))}
          </div>
        </div>

        {apiKey.is_active && !isExpired && (
          <div className="flex items-center gap-1 ml-4 shrink-0">
            <button
              onClick={handleRotate}
              disabled={rotateKey.isPending}
              className="p-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface-2)] rounded transition-colors"
              title="轮换"
            >
              <RefreshCw
                className={`h-4 w-4 ${rotateKey.isPending ? "animate-spin" : ""}`}
              />
            </button>
            {confirmRevoke ? (
              <div className="flex items-center gap-1">
                <button
                  onClick={handleRevoke}
                  disabled={revokeKey.isPending}
                  className="px-2 py-1 text-xs text-[var(--color-error)] bg-[var(--color-surface-2)] hover:opacity-80 rounded transition-colors"
                >
                  确认撤销
                </button>
                <button
                  onClick={() => setConfirmRevoke(false)}
                  className="px-2 py-1 text-xs text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-2)] rounded transition-colors"
                >
                  取消
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmRevoke(true)}
                className="p-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-error)] hover:bg-[var(--color-surface-2)] rounded transition-colors"
                title="撤销"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
      </div>

      {showReveal && (
        <KeyRevealDialog
          rawKey={showReveal}
          onClose={() => setShowReveal(null)}
        />
      )}
    </>
  );
}

// ── Agent Guide Section ──────────────────────────────────────────────────────

function AgentGuideSection() {
  const [copiedSnippet, setCopiedSnippet] = useState<string | null>(null);

  const copySnippet = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedSnippet(id);
    setTimeout(() => setCopiedSnippet(null), 2000);
  };

  const curlExample = `curl -H "X-API-Key: isk_YOUR_KEY_HERE" \\
  https://your-domain.com/api/goals`;

  const pythonExample = `import urllib.request
import json

API_KEY = "isk_YOUR_KEY_HERE"
BASE_URL = "https://your-domain.com/api"

req = urllib.request.Request(
    f"{BASE_URL}/goals",
    headers={"X-API-Key": API_KEY}
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
    print(data)`;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-[var(--color-accent)]" />
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
            Agent 接入指南
          </h2>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* Authentication */}
          <div>
            <h3 className="text-sm font-medium text-[var(--color-text-primary)] mb-2">
              1. 认证方式
            </h3>
            <p className="text-sm text-[var(--color-text-secondary)] mb-2">
              在请求头中传递 <code className="bg-[var(--color-surface-2)] px-1.5 py-0.5 rounded text-xs font-mono">X-API-Key</code> 即可：
            </p>
            <div className="relative">
              <pre className="bg-gray-900 text-green-400 text-xs p-3 rounded-lg overflow-x-auto">
                {curlExample}
              </pre>
              <button
                onClick={() => copySnippet(curlExample, "curl")}
                className="absolute top-2 right-2 p-1 text-gray-400 hover:text-white rounded"
              >
                {copiedSnippet === "curl" ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          </div>

          {/* Python Example */}
          <div>
            <h3 className="text-sm font-medium text-[var(--color-text-primary)] mb-2">
              2. Python 示例（纯标准库）
            </h3>
            <div className="relative">
              <pre className="bg-gray-900 text-green-400 text-xs p-3 rounded-lg overflow-x-auto">
                {pythonExample}
              </pre>
              <button
                onClick={() => copySnippet(pythonExample, "python")}
                className="absolute top-2 right-2 p-1 text-gray-400 hover:text-white rounded"
              >
                {copiedSnippet === "python" ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          </div>

          {/* OpenAPI */}
          <div>
            <h3 className="text-sm font-medium text-[var(--color-text-primary)] mb-2">
              3. OpenAPI 文档
            </h3>
            <p className="text-sm text-[var(--color-text-secondary)]">
              完整的 API 文档可在以下地址查看（无需认证）：
            </p>
            <div className="mt-2 space-y-1">
              <a
                href="/api/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="block text-sm text-[var(--color-accent)] hover:opacity-80 underline"
              >
                Swagger UI &rarr; /api/docs
              </a>
              <a
                href="/api/redoc"
                target="_blank"
                rel="noopener noreferrer"
                className="block text-sm text-[var(--color-accent)] hover:opacity-80 underline"
              >
                ReDoc &rarr; /api/redoc
              </a>
              <a
                href="/api/openapi.json"
                target="_blank"
                rel="noopener noreferrer"
                className="block text-sm text-[var(--color-accent)] hover:opacity-80 underline"
              >
                OpenAPI JSON &rarr; /api/openapi.json
              </a>
            </div>
          </div>

          {/* Scopes */}
          <div>
            <h3 className="text-sm font-medium text-[var(--color-text-primary)] mb-2">
              4. 权限 Scope 说明
            </h3>
            <div className="bg-[var(--color-surface-2)] rounded-lg p-3">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[var(--color-text-tertiary)]">
                    <th className="pb-2 font-medium">Scope</th>
                    <th className="pb-2 font-medium">说明</th>
                  </tr>
                </thead>
                <tbody className="text-[var(--color-text-secondary)]">
                  {API_KEY_SCOPES.map((scope) => (
                    <tr key={scope.value} className="border-t border-[var(--color-border)]">
                      <td className="py-1.5 font-mono">{scope.value}</td>
                      <td className="py-1.5">{scope.label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function DevelopersPage() {
  const { data, isLoading, error } = useApiKeys();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [revealKey, setRevealKey] = useState<string | null>(null);

  const handleKeyCreated = (rawKey: string) => {
    setShowCreateDialog(false);
    setRevealKey(rawKey);
  };

  return (
    <PageShell className="space-y-6">
      <PageHeader
        title="开发者中心"
        description="管理 API Keys 并了解如何通过 Agent 接入 infoSentry"
      />

      <div className="space-y-6">
        {/* API Keys Management */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-[var(--color-accent)]" />
                <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
                  API Keys
                </h2>
              </div>
              <Button
                size="sm"
                onClick={() => setShowCreateDialog(true)}
              >
                <Plus className="h-4 w-4 mr-1" />
                创建 Key
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-8 text-center text-sm text-[var(--color-text-tertiary)]">
                加载中...
              </div>
            ) : error ? (
              <Alert variant="error">
                加载失败：{(error as Error)?.message || "未知错误"}
              </Alert>
            ) : !data?.keys.length ? (
              <div className="py-8 text-center">
                <Key className="h-8 w-8 text-[var(--color-text-tertiary)] mx-auto mb-2" />
                <p className="text-sm text-[var(--color-text-tertiary)] mb-3">
                  还没有创建任何 API Key
                </p>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowCreateDialog(true)}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  创建第一个 Key
                </Button>
              </div>
            ) : (
              <div>
                {data.keys.map((key) => (
                  <ApiKeyRow key={key.id} apiKey={key} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Agent Integration Guide */}
        <AgentGuideSection />
      </div>

      {/* Dialogs */}
      {showCreateDialog && (
        <CreateKeyDialog
          onClose={() => setShowCreateDialog(false)}
          onCreated={handleKeyCreated}
        />
      )}
      {revealKey && (
        <KeyRevealDialog
          rawKey={revealKey}
          onClose={() => setRevealKey(null)}
        />
      )}
    </PageShell>
  );
}

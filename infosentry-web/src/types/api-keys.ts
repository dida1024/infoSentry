/**
 * API Key 相关类型定义
 */

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export interface ApiKeyCreated {
  key: ApiKey;
  raw_key: string;
}

export interface ApiKeyList {
  keys: ApiKey[];
  total: number;
}

export interface CreateApiKeyRequest {
  name: string;
  scopes: string[];
  expires_in_days?: number | null;
}

/** 可用的 API Key scope */
export const API_KEY_SCOPES = [
  { value: "goals:read", label: "目标 (读取)", group: "目标" },
  { value: "goals:write", label: "目标 (写入)", group: "目标" },
  { value: "sources:read", label: "信息源 (读取)", group: "信息源" },
  { value: "sources:write", label: "信息源 (写入)", group: "信息源" },
  { value: "notifications:read", label: "通知 (读取)", group: "通知" },
  { value: "notifications:write", label: "通知 (写入)", group: "通知" },
  { value: "agent:read", label: "Agent (读取)", group: "Agent" },
  { value: "admin:read", label: "管理员 (读取)", group: "管理" },
  { value: "admin:write", label: "管理员 (写入)", group: "管理" },
] as const;

export type ApiKeyScope = (typeof API_KEY_SCOPES)[number]["value"];

/**
 * 应用常量
 */

// API 配置
const ensureApiBaseUrl = (value: string): string => {
  const trimmed = value.replace(/\/+$/, "");
  if (trimmed.endsWith("/api/v1")) {
    return trimmed;
  }
  return `${trimmed}/api/v1`;
};

export const API_BASE_URL = ensureApiBaseUrl(
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
);

export const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

// 应用信息
export const APP_NAME = "infoSentry";
export const APP_DESCRIPTION = "智能信息追踪与推送系统";

// 分页默认值
export const DEFAULT_PAGE_SIZE = 20;

// Goal 相关
export const PRIORITY_MODES = {
  STRICT: "STRICT",
  SOFT: "SOFT",
} as const;

export const GOAL_STATUS = {
  ACTIVE: "active",
  PAUSED: "paused",
  ARCHIVED: "archived",
} as const;

// Push 决策类型
export const PUSH_DECISION = {
  IMMEDIATE: "IMMEDIATE",
  BATCH: "BATCH",
  DIGEST: "DIGEST",
  IGNORE: "IGNORE",
} as const;

// 反馈类型
export const FEEDBACK_TYPE = {
  LIKE: "LIKE",
  DISLIKE: "DISLIKE",
} as const;

// Source 类型
export const SOURCE_TYPE = {
  NEWSNOW: "NEWSNOW",
  RSS: "RSS",
  SITE: "SITE",
} as const;

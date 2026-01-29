/**
 * 公共类型定义
 */

// API 响应基础类型
export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// 用户
export interface User {
  id: string;
  email: string;
  display_name?: string;
  timezone?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}

// Goal
export type GoalStatus = "active" | "paused" | "archived";
export type PriorityMode = "STRICT" | "SOFT";

export interface GoalStats {
  total_matches: number;
  immediate_count: number;
  batch_count: number;
  digest_count: number;
}

/**
 * 后端 GoalResponse（GET /goals, GET /goals/{id} 的 data 单项）
 */
export interface Goal {
  id: string;
  name: string;
  description: string;
  status: GoalStatus;
  priority_mode: PriorityMode;
  priority_terms: string[] | null;
  negative_terms: string[] | null;
  batch_enabled: boolean;
  batch_windows: string[] | null;
  digest_send_time: string | null;
  stats: GoalStats | null;
  created_at: string;
  updated_at: string;
}

export type GoalDetail = Goal;

// Source
export interface Source {
  id: string;
  type: "NEWSNOW" | "RSS" | "SITE";
  name: string;
  is_private: boolean;
  enabled: boolean;
  fetch_interval_sec: number;
  last_fetch_at?: string;
  next_fetch_at?: string;
  error_streak: number;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PublicSource extends Source {
  is_subscribed: boolean;
}

// Item
export interface Item {
  id: string;
  source_id: string;
  url: string;
  title: string;
  snippet?: string;
  summary?: string;
  published_at?: string;
  ingested_at: string;
  source_name?: string;
}

// Goal-Item 匹配
export interface GoalItemMatch {
  id: string;
  goal_id: string;
  item_id: string;
  match_score: number;
  features_json: Record<string, unknown>;
  reasons_json: Record<string, unknown>;
  computed_at: string;
  item?: Item;
}

// 推送决策
export interface PushDecision {
  id: string;
  goal_id: string;
  item_id: string;
  decision: "IMMEDIATE" | "BATCH" | "DIGEST" | "IGNORE";
  status: "PENDING" | "SENT" | "FAILED" | "SKIPPED" | "READ";
  channel: "EMAIL" | "IN_APP";
  reason_json: {
    reason?: string;
    evidence?: Array<{
      type: string;
      value: string;
      ref?: Record<string, string>;
    }>;
  };
  decided_at: string;
  sent_at?: string;
  item?: Item;
  goal?: Goal;
}

// Notification（用于 Inbox 展示）
export interface Notification extends PushDecision {
  item: Item;
  goal_id: string;
  goal?: Goal;
}

// 反馈
export interface ItemFeedback {
  id: string;
  item_id: string;
  goal_id: string;
  user_id: string;
  feedback: "LIKE" | "DISLIKE";
  block_source: boolean;
  created_at: string;
}

/**
 * Notifications API
 */
import { api } from "./client";
import type { ApiResponse, PushDecision, Item, Goal } from "@/types";

export interface FeedbackRequest {
  goal_id: string;
  feedback: "LIKE" | "DISLIKE";
  block_source?: boolean;
}

// 后端返回的通知项格式
interface NotificationItem {
  id: string;
  goal_id: string;
  item_id: string;
  decision: string;
  status: string;
  channel: string;
  item: {
    title: string;
    url: string;
    source_name?: string;
    published_at?: string;
    snippet?: string;
  };
  reason?: {
    summary: string;
    score: number;
    evidence: Array<{
      type: string;
      value: string;
      quote?: string;
      ref?: Record<string, string>;
    }>;
  };
  actions: Array<{
    type: string;
    url?: string;
  }>;
  decided_at: string;
  sent_at?: string;
}

// 后端返回的通知列表响应格式
interface NotificationListPayload {
  notifications: NotificationItem[];
  next_cursor?: string;
  has_more: boolean;
}

interface FeedbackResponse {
  ok: boolean;
  feedback_id: string;
}

// 转换为前端 Notification 类型
interface Notification extends PushDecision {
  item: Item;
  goal?: Goal;
}

// Cursor 分页响应
export interface CursorPaginatedResponse<T> {
  items: T[];
  next_cursor?: string;
  has_more: boolean;
}

export const notificationsApi = {
  /**
   * 获取通知列表（cursor 分页）
   */
  list: async (params?: {
    goal_id?: string;
    status?: string;
    cursor?: string;
    page_size?: number;
  }): Promise<CursorPaginatedResponse<Notification>> => {
    const response = await api.get<ApiResponse<NotificationListPayload>>(
      "/notifications",
      { params }
    );
    const payload = response.data;

    // 转换为前端期望的格式
    const items: Notification[] = payload.notifications.map((n) => ({
      id: n.id,
      goal_id: n.goal_id,
      item_id: n.item_id,
      decision: n.decision as "IMMEDIATE" | "BATCH" | "DIGEST" | "IGNORE",
      status: n.status as "PENDING" | "SENT" | "FAILED" | "SKIPPED" | "READ",
      channel: n.channel as "EMAIL" | "IN_APP",
      reason_json: {
        reason: n.reason?.summary,
        evidence: n.reason?.evidence?.map((e) => ({
          type: e.type,
          value: e.value,
          ref: e.ref,
        })),
      },
      decided_at: n.decided_at,
      sent_at: n.sent_at,
      item: {
        id: n.item_id,
        source_id: "",
        url: n.item.url,
        title: n.item.title,
        snippet: n.item.snippet,
        published_at: n.item.published_at,
        ingested_at: n.decided_at,
        source_name: n.item.source_name,
      },
    }));

    return {
      items,
      next_cursor: payload.next_cursor,
      has_more: payload.has_more,
    };
  },

  /**
   * 获取单个通知 (暂不支持)
   */
  get: async (id: string): Promise<Notification> => {
    throw new Error(`Notification ${id} detail not implemented`);
  },

  /**
   * 标记通知为已读
   */
  markAsRead: (id: string) => api.post<void>(`/notifications/${id}/read`),

  /**
   * 提交反馈
   */
  submitFeedback: async (
    itemId: string,
    data: FeedbackRequest
  ): Promise<FeedbackResponse> => {
    const response = await api.post<ApiResponse<FeedbackResponse>>(
      `/items/${itemId}/feedback`,
      data
    );
    return response.data;
  },
};


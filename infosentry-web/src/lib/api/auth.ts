/**
 * 认证 API
 */
import { api } from "./client";
import type { User } from "@/types";

export interface RequestMagicLinkRequest {
  email: string;
}

export interface RequestMagicLinkResponse {
  ok: boolean;
  message: string;
}

export interface SessionResponse {
  user_id: string;
  email: string;
  access_token: string;
  expires_at: string;
}

export interface ConsumeMagicLinkApiResponse {
  ok: boolean;
  session: SessionResponse;
}

export interface ConsumeMagicLinkResponse {
  access_token: string;
  user: User;
}

export const authApi = {
  /**
   * 请求发送 Magic Link
   */
  requestMagicLink: (data: RequestMagicLinkRequest) =>
    api.post<RequestMagicLinkResponse>("/auth/request_link", data),

  /**
   * 消费 Magic Link Token
   */
  consumeMagicLink: async (token: string): Promise<ConsumeMagicLinkResponse> => {
    const response = await api.get<ConsumeMagicLinkApiResponse>(`/auth/consume?token=${token}`);
    return {
      access_token: response.session.access_token,
      user: {
        id: response.session.user_id,
        email: response.session.email,
      },
    };
  },

  /**
   * 获取当前用户信息
   */
  getCurrentUser: async (): Promise<User> => {
    const response = await api.get<{ code: number; data: User }>("/users/me");
    return response.data;
  },
};


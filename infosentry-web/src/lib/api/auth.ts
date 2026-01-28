/**
 * 认证 API
 */
import { api } from "./client";
import type { ApiResponse, User } from "@/types";

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

export interface RefreshSessionResponse {
  ok: boolean;
  access_token: string;
  expires_at: string;
}

export interface LogoutResponse {
  ok: boolean;
  message: string;
}

export interface UpdateProfileRequest {
  display_name?: string;
  timezone?: string;
}

export interface UpdateProfileResponse {
  ok: boolean;
  user: User;
}

export const authApi = {
  /**
   * 请求发送 Magic Link
   */
  requestMagicLink: async (
    data: RequestMagicLinkRequest
  ): Promise<RequestMagicLinkResponse> => {
    const response = await api.post<ApiResponse<RequestMagicLinkResponse>>(
      "/auth/request_link",
      data
    );
    return response.data;
  },

  /**
   * 消费 Magic Link Token
   */
  consumeMagicLink: async (token: string): Promise<ConsumeMagicLinkResponse> => {
    const response = await api.get<ApiResponse<ConsumeMagicLinkApiResponse>>(
      `/auth/consume?token=${token}`
    );
    return {
      access_token: response.data.session.access_token,
      user: {
        id: response.data.session.user_id,
        email: response.data.session.email,
      },
    };
  },

  /**
   * 获取当前用户信息
   */
  getCurrentUser: async (): Promise<User> => {
    const response = await api.get<{ code: number; data: User }>(
      "/users/me",
      { skipAuthRedirect: true }
    );
    return response.data;
  },

  /**
   * 刷新登录会话
   */
  refreshSession: async (): Promise<RefreshSessionResponse> => {
    const response = await api.post<ApiResponse<RefreshSessionResponse>>(
      "/auth/refresh",
      undefined,
      {
        skipAuthRedirect: true,
        skipAuthClear: true,
      }
    );
    return response.data;
  },

  /**
   * 退出登录
   */
  logout: async (): Promise<LogoutResponse> => {
    const response = await api.post<ApiResponse<LogoutResponse>>(
      "/auth/logout",
      undefined,
      {
        skipAuthRedirect: true,
      }
    );
    return response.data;
  },

  /**
   * 更新用户资料
   */
  updateProfile: async (data: UpdateProfileRequest): Promise<User> => {
    const response = await api.put<{ code: number; data: User }>(
      "/users/me",
      data
    );
    return response.data;
  },
};


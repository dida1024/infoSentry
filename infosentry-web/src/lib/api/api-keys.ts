/**
 * API Keys API
 */
import { api } from "./client";
import type {
  ApiKey,
  ApiKeyCreated,
  ApiKeyList,
  CreateApiKeyRequest,
} from "@/types/api-keys";

interface ApiWrapper<T> {
  code: number;
  message?: string;
  data: T;
}

export const apiKeysApi = {
  /**
   * 获取当前用户的所有 API Keys
   */
  list: async (): Promise<ApiKeyList> => {
    const response = await api.get<ApiWrapper<ApiKeyList>>("/keys");
    return response.data;
  },

  /**
   * 创建新的 API Key
   */
  create: async (data: CreateApiKeyRequest): Promise<ApiKeyCreated> => {
    const response = await api.post<ApiWrapper<ApiKeyCreated>>("/keys", data);
    return response.data;
  },

  /**
   * 撤销 API Key
   */
  revoke: async (keyId: string): Promise<ApiKey> => {
    const response = await api.delete<ApiWrapper<ApiKey>>(`/keys/${keyId}`);
    return response.data;
  },

  /**
   * 轮换 API Key
   */
  rotate: async (keyId: string): Promise<ApiKeyCreated> => {
    const response = await api.post<ApiWrapper<ApiKeyCreated>>(
      `/keys/${keyId}/rotate`
    );
    return response.data;
  },
};

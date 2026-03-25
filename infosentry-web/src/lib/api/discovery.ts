import { API_BASE_URL } from "@/lib/constants";
import type {
  DiscoverySession,
  DiscoveryStreamEvent,
  PaginatedResponse,
} from "@/types";
import { api } from "./client";

interface ApiWrapper<T> {
  code: number;
  message?: string;
  data: T;
}

interface PaginatedApiWrapper<T> {
  code: number;
  data: T[];
  meta: {
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  };
}

export interface CreateDiscoverySessionRequest {
  query: string;
}

export interface SendDiscoveryMessageRequest {
  content: string;
}

interface StreamDiscoveryOptions {
  signal?: AbortSignal;
  onEvent: (event: DiscoveryStreamEvent) => void;
}

const getAuthHeader = (): Record<string, string> => {
  if (typeof window === "undefined") {
    return {};
  }
  const token = window.localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const parseSseChunk = (chunk: string): DiscoveryStreamEvent | null => {
  const lines = chunk
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  let eventName = "";
  const dataParts: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataParts.push(line.slice("data:".length).trim());
    }
  }

  if (!eventName || dataParts.length === 0) {
    return null;
  }

  try {
    return {
      event: eventName,
      data: JSON.parse(dataParts.join("\n")),
    } as DiscoveryStreamEvent;
  } catch {
    return null;
  }
};

export const discoveryApi = {
  createSession: async (
    data: CreateDiscoverySessionRequest
  ): Promise<DiscoverySession> => {
    const response = await api.post<ApiWrapper<DiscoverySession>>(
      "/discovery/sessions",
      data
    );
    return response.data;
  },

  getSession: async (sessionId: string): Promise<DiscoverySession> => {
    const response = await api.get<ApiWrapper<DiscoverySession>>(
      `/discovery/sessions/${sessionId}`
    );
    return response.data;
  },

  listSessions: async (params?: {
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<DiscoverySession>> => {
    const response = await api.get<PaginatedApiWrapper<DiscoverySession>>(
      "/discovery/sessions",
      { params }
    );
    return {
      items: response.data,
      total: response.meta.total,
      page: response.meta.page,
      page_size: response.meta.page_size,
      total_pages: response.meta.total_pages,
    };
  },

  sendMessage: async (
    sessionId: string,
    data: SendDiscoveryMessageRequest
  ): Promise<DiscoverySession> => {
    const response = await api.post<ApiWrapper<DiscoverySession>>(
      `/discovery/sessions/${sessionId}/messages`,
      data
    );
    return response.data;
  },

  streamSession: async (
    sessionId: string,
    options: StreamDiscoveryOptions
  ): Promise<void> => {
    const response = await fetch(
      `${API_BASE_URL}/discovery/sessions/${sessionId}/stream`,
      {
        method: "GET",
        headers: {
          Accept: "text/event-stream",
          ...getAuthHeader(),
        },
        credentials: "include",
        signal: options.signal,
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || "无法建立发现信息源的实时连接");
    }

    if (!response.body) {
      throw new Error("浏览器不支持实时流式响应");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() ?? "";

      for (const chunk of chunks) {
        const event = parseSseChunk(chunk);
        if (event) {
          options.onEvent(event);
        }
      }
    }

    if (buffer.trim()) {
      const event = parseSseChunk(buffer);
      if (event) {
        options.onEvent(event);
      }
    }
  },
};

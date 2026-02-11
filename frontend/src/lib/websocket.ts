// KotobaTranscriber WebSocket client with auto-reconnect

import type { WsEvent } from "./types";
import { wsConnected } from "./stores";
import { getApiToken } from "./api";

type EventHandler = (event: WsEvent) => void;

/** Type-safe accessor for WsEvent data fields */
export function getEventData<T>(event: WsEvent): T {
  return event.data as unknown as T;
}

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string = "";
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private globalHandlers: Set<EventHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private shouldReconnect = true;

  /** Start WebSocket connection */
  connect(url: string) {
    this.url = url;
    this.shouldReconnect = true;
    this._connect();
  }

  /** Disconnect */
  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    wsConnected.set(false);
  }

  /** Subscribe to specific event type */
  on(eventType: string, handler: EventHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);

    return () => {
      this.handlers.get(eventType)?.delete(handler);
    };
  }

  /** Subscribe to all events */
  onAny(handler: EventHandler): () => void {
    this.globalHandlers.add(handler);
    return () => {
      this.globalHandlers.delete(handler);
    };
  }

  /** Connection state */
  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private _connect() {
    if (
      this.ws?.readyState === WebSocket.OPEN ||
      this.ws?.readyState === WebSocket.CONNECTING
    )
      return;

    try {
      const token = getApiToken();
      const wsUrl = token ? `${this.url}?token=${encodeURIComponent(token)}` : this.url;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("[WS] Connected");
        this.reconnectDelay = 1000;
        wsConnected.set(true);
      };

      this.ws.onmessage = (msg) => {
        try {
          const event: WsEvent = JSON.parse(msg.data);
          this._dispatch(event);
        } catch (e) {
          console.error("[WS] Parse error:", e);
        }
      };

      this.ws.onclose = () => {
        console.log("[WS] Disconnected");
        wsConnected.set(false);
        this._scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.error("[WS] Error:", err);
      };
    } catch (e) {
      console.error("[WS] Connection failed:", e);
      this._scheduleReconnect();
    }
  }

  private _dispatch(event: WsEvent) {
    const typeHandlers = this.handlers.get(event.type);
    if (typeHandlers) {
      for (const handler of typeHandlers) {
        try {
          handler(event);
        } catch (e) {
          console.error(`[WS] Handler error for '${event.type}':`, e);
        }
      }
    }

    for (const handler of this.globalHandlers) {
      try {
        handler(event);
      } catch (e) {
        console.error("[WS] Global handler error:", e);
      }
    }
  }

  private _scheduleReconnect() {
    if (!this.shouldReconnect) return;
    if (this.reconnectTimer) return;

    console.log(`[WS] Reconnecting in ${this.reconnectDelay}ms...`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this._connect();
    }, this.reconnectDelay);

    this.reconnectDelay = Math.min(
      this.reconnectDelay * 2,
      this.maxReconnectDelay
    );
  }
}

export const ws = new WebSocketClient();

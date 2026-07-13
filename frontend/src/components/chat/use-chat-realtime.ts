"use client";

import { useEffect, useState } from "react";

import { useToast } from "@/components/ui/toast-provider";
import type { RealtimeEvent } from "@/lib/chat/types";

type RealtimeSocketFactory = (after?: number) => Promise<WebSocket>;

const RECONNECT_DELAY = 1200;
const TOAST_DELAY = 1800;

export function useChatRealtime(
  createSocket: RealtimeSocketFactory,
  onEvent: (event: RealtimeEvent) => void,
  onReady: () => void,
) {
  const { dismissToast, showToast } = useToast();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | undefined;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let toastTimer: ReturnType<typeof setTimeout> | undefined;
    let cursor = 0;

    function clearToastDelay() {
      if (!toastTimer) return;
      clearTimeout(toastTimer);
      toastTimer = undefined;
    }

    function scheduleReconnectToast() {
      if (toastTimer) return;
      toastTimer = setTimeout(() => {
        toastTimer = undefined;
        if (cancelled) return;
        showToast({
          id: "realtime-connection",
          message: "リアルタイム接続を再試行しています。",
          tone: "warning",
          duration: null,
        });
      }, TOAST_DELAY);
    }

    async function connect(after?: number) {
      setReady(false);
      try {
        const nextSocket = await createSocket(after);
        if (cancelled) {
          nextSocket.close();
          return;
        }
        socket = nextSocket;
        socket.addEventListener("message", (messageEvent) => {
          const payload = JSON.parse(messageEvent.data as string) as
            | RealtimeEvent
            | { type: "ready" | "ping"; cursor?: number };
          if (payload.type === "ready") {
            cursor = Math.max(cursor, payload.cursor ?? 0);
            setReady(true);
            onReady();
            clearToastDelay();
            dismissToast("realtime-connection");
          } else if (payload.type !== "ping" && "sequence" in payload) {
            cursor = Math.max(cursor, payload.sequence);
            onEvent(payload);
          }
        });
        socket.addEventListener("close", () => {
          if (cancelled) return;
          setReady(false);
          scheduleReconnectToast();
          reconnectTimer = setTimeout(
            () => void connect(cursor),
            RECONNECT_DELAY,
          );
        });
      } catch {
        if (cancelled) return;
        setReady(false);
        scheduleReconnectToast();
        reconnectTimer = setTimeout(
          () => void connect(cursor),
          RECONNECT_DELAY,
        );
      }
    }

    void connect();
    return () => {
      cancelled = true;
      socket?.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      clearToastDelay();
      dismissToast("realtime-connection");
    };
  }, [createSocket, dismissToast, onEvent, onReady, showToast]);

  return ready;
}

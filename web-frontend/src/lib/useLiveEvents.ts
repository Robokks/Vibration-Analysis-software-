import { useEffect, useRef, useState } from "react";
import { API_BASE_URL, type LiveEvent } from "./api";

// The `/live/ws` relay lives on the same backend host as the REST API --
// derive the WS base by swapping the scheme so a single VITE_API_BASE_URL
// configures both surfaces (http://... -> ws://..., https://... -> wss://...).
const WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws");

const RECONNECT_DELAY_MS = 2000;

type LiveStatus = "connecting" | "open" | "closed";

/** Opens a WebSocket to `${WS_BASE_URL}/live/ws`, JSON-parses each message
 * frame, and hands the decoded `LiveEvent` off to `onEvent`. Reconnects with
 * a bounded 2s backoff on close so a backend restart or dropped socket
 * doesn't leave the Live Display dark.
 *
 * The onEvent callback is stored in a ref so the parent can pass an inline
 * closure without tearing the WebSocket down every render -- the effect's
 * dependency array is [] on purpose: the socket's lifecycle is tied to
 * component mount, not to whatever function the parent constructed this
 * render. */
export function useLiveEvents(onEvent: (event: LiveEvent) => void): { status: LiveStatus; error: string | null } {
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;

    function connect() {
      if (cancelled) return;
      setStatus("connecting");

      const ws = new WebSocket(`${WS_BASE_URL}/live/ws`);
      socket = ws;

      ws.onopen = () => {
        if (cancelled) return;
        setStatus("open");
        setError(null);
      };

      ws.onmessage = (message) => {
        if (cancelled) return;
        try {
          const event = JSON.parse(message.data) as LiveEvent;
          onEventRef.current(event);
        } catch (err) {
          // A malformed frame shouldn't kill the stream -- log and keep
          // reading. The backend produces from a pydantic model, so this
          // is only reached if something upstream is broken.
          const detail = err instanceof Error ? err.message : "invalid JSON";
          setError(`Failed to parse live event: ${detail}`);
        }
      };

      ws.onerror = () => {
        if (cancelled) return;
        setError("WebSocket error (is the backend running?)");
      };

      ws.onclose = () => {
        if (cancelled) return;
        setStatus("closed");
        reconnectTimer = window.setTimeout(connect, RECONNECT_DELAY_MS);
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close();
      }
    };
  }, []);

  return { status, error };
}

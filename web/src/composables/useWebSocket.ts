import { ref } from "vue";
import { useUserStore, useNotificationStore } from "@/stores";
import { notification } from "@/components/vort/notification";

export type WsMessageHandler = (data: any) => void;

const ws = ref<WebSocket | null>(null);
const connected = ref(false);
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectDelay = 1000;
const MAX_RECONNECT_DELAY = 30000;
const handlers = new Map<string, Set<WsMessageHandler>>();
let initialized = false;

const PING_INTERVAL = 25000;
const PONG_TIMEOUT = 10000;
let pingTimer: ReturnType<typeof setInterval> | null = null;
let pongTimer: ReturnType<typeof setTimeout> | null = null;

function getWsUrl(token: string): string {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}/api/ws?token=${encodeURIComponent(token)}`;
}

function tryNotify(data: any) {
    try {
        const msgType = data?.type;
        if (msgType === "schedule_result" || msgType === "message") {
            const senderName = data.executor_name || data.sender_name || "AI";
            const summary = data.result || data.content || "";
            const type = data.severity === "error" ? "error" as const : "info" as const;
            notification[type]({
                message: senderName,
                description: (summary as string).slice(0, 120),
                duration: 5000,
            });
        }
    } catch { /* silent */ }
}

function dispatchMessage(data: any) {
    const msgType = data?.type;
    if (!msgType) return;

    if (msgType === "pong") {
        clearPongTimeout();
        return;
    }

    const notificationStore = useNotificationStore();

    if (msgType === "unread_update") {
        notificationStore.setUnread(data.session_id, data.count ?? 0);
    } else if (msgType === "task_status") {
        notificationStore.setTaskStatus(data.member_id, data.status, data.job_name ?? "");
    } else if (msgType === "task_completed" || msgType === "task_failed") {
        if (data.member_id) {
            notificationStore.setTaskStatus(data.member_id, "idle");
        }
    } else if (msgType === "vortflow_notification") {
        notificationStore.incrementVortflowUnread();
        notification.info({
            message: data.title || "VortFlow",
            description: (data.message || "").slice(0, 120),
            duration: 5000,
        });
    }

    if (msgType === "schedule_result" || msgType === "message" || msgType === "task_completed" || msgType === "task_failed") {
        tryNotify(data);
    }

    const typeHandlers = handlers.get(msgType);
    if (typeHandlers) {
        typeHandlers.forEach((h) => {
            try { h(data); } catch { /* noop */ }
        });
    }
    const allHandlers = handlers.get("*");
    if (allHandlers) {
        allHandlers.forEach((h) => {
            try { h(data); } catch { /* noop */ }
        });
    }
}

function startHeartbeat() {
    stopHeartbeat();
    pingTimer = setInterval(() => {
        if (ws.value && ws.value.readyState === WebSocket.OPEN) {
            try {
                ws.value.send(JSON.stringify({ type: "ping" }));
            } catch {
                forceReconnect();
                return;
            }
            pongTimer = setTimeout(() => {
                forceReconnect();
            }, PONG_TIMEOUT);
        }
    }, PING_INTERVAL);
}

function clearPongTimeout() {
    if (pongTimer) {
        clearTimeout(pongTimer);
        pongTimer = null;
    }
}

function stopHeartbeat() {
    if (pingTimer) {
        clearInterval(pingTimer);
        pingTimer = null;
    }
    clearPongTimeout();
}

function forceReconnect() {
    stopHeartbeat();
    if (ws.value) {
        try { ws.value.close(); } catch { /* noop */ }
        ws.value = null;
    }
    connected.value = false;
    scheduleReconnect();
}

function doConnect() {
    const userStore = useUserStore();
    const token = userStore.token;
    if (!token) return;

    try {
        const socket = new WebSocket(getWsUrl(token));

        socket.onopen = () => {
            connected.value = true;
            reconnectDelay = 1000;
            startHeartbeat();

            const notificationStore = useNotificationStore();
            notificationStore.fetchUnreadCounts();

            const reconnectHandlers = handlers.get("_reconnected");
            if (reconnectHandlers) {
                reconnectHandlers.forEach((h) => {
                    try { h({}); } catch { /* noop */ }
                });
            }
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                dispatchMessage(data);
            } catch { /* ignore non-JSON */ }
        };

        socket.onclose = () => {
            connected.value = false;
            ws.value = null;
            stopHeartbeat();
            scheduleReconnect();
        };

        socket.onerror = () => {
            socket.close();
        };

        ws.value = socket;
    } catch {
        scheduleReconnect();
    }
}

function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        const userStore = useUserStore();
        if (userStore.token) doConnect();
    }, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
}

export function initWebSocket() {
    if (initialized) return;
    initialized = true;
    doConnect();
}

export function closeWebSocket() {
    initialized = false;
    stopHeartbeat();
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    if (ws.value) {
        ws.value.close();
        ws.value = null;
    }
    connected.value = false;
}

export function useWebSocket() {
    function on(type: string, handler: WsMessageHandler) {
        if (!handlers.has(type)) handlers.set(type, new Set());
        handlers.get(type)!.add(handler);
    }

    function off(type: string, handler: WsMessageHandler) {
        handlers.get(type)?.delete(handler);
    }

    function send(data: any) {
        if (ws.value && ws.value.readyState === WebSocket.OPEN) {
            ws.value.send(JSON.stringify(data));
        }
    }

    return { connected, on, off, send, initWebSocket, closeWebSocket };
}

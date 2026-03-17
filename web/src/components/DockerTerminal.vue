<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from "vue";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";
import { useUserStore } from "@/stores/modules/user";

const props = defineProps<{ nodeId: string }>();
const userStore = useUserStore();

const containerRef = ref<HTMLDivElement>();
let terminal: Terminal | null = null;
let fitAddon: FitAddon | null = null;
let ws: WebSocket | null = null;
let resizeObserver: ResizeObserver | null = null;

const connected = ref(false);
const error = ref("");

function getWsUrl() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const token = encodeURIComponent(userStore.token);
    return `${proto}//${location.host}/api/admin/remote-nodes/${props.nodeId}/terminal?token=${token}`;
}

function connect() {
    if (!containerRef.value) return;

    terminal = new Terminal({
        cursorBlink: true,
        fontSize: 13,
        fontFamily: '"Fira Code", "JetBrains Mono", "Cascadia Code", monospace',
        theme: {
            background: "#1e1e2e",
            foreground: "#cdd6f4",
            cursor: "#f5e0dc",
            selectionBackground: "#585b7066",
        },
        scrollback: 5000,
        convertEol: true,
    });

    fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.loadAddon(new WebLinksAddon());
    terminal.open(containerRef.value);

    nextTick(() => fitAddon?.fit());

    ws = new WebSocket(getWsUrl());
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        connected.value = true;
        error.value = "";
        terminal?.focus();
    };

    ws.onmessage = (ev) => {
        if (ev.data instanceof ArrayBuffer) {
            terminal?.write(new Uint8Array(ev.data));
        } else {
            terminal?.write(ev.data);
        }
    };

    ws.onclose = (ev) => {
        connected.value = false;
        if (ev.code === 4000 || ev.code === 4001 || ev.code === 4002) {
            error.value = ev.reason || "连接被拒绝";
        }
        terminal?.write("\r\n\x1b[90m[连接已断开]\x1b[0m\r\n");
    };

    ws.onerror = () => {
        error.value = "WebSocket 连接失败";
    };

    terminal.onData((data) => {
        if (ws?.readyState === WebSocket.OPEN) {
            ws.send(data);
        }
    });

    terminal.onResize(({ cols, rows }) => {
        if (ws?.readyState === WebSocket.OPEN) {
            const resizeMsg = new Uint8Array([0x01, ...new TextEncoder().encode(JSON.stringify({ cols, rows }))]);
            ws.send(resizeMsg);
        }
    });

    resizeObserver = new ResizeObserver(() => {
        try { fitAddon?.fit(); } catch { /* ignore */ }
    });
    resizeObserver.observe(containerRef.value);
}

function disconnect() {
    resizeObserver?.disconnect();
    resizeObserver = null;
    ws?.close();
    ws = null;
    terminal?.dispose();
    terminal = null;
    fitAddon = null;
}

onMounted(connect);
onBeforeUnmount(disconnect);
</script>

<template>
    <div class="docker-terminal">
        <div v-if="error" class="text-red-500 text-sm mb-2">{{ error }}</div>
        <div ref="containerRef" class="terminal-container" />
    </div>
</template>

<style scoped>
.docker-terminal {
    width: 100%;
}
.terminal-container {
    width: 100%;
    height: 480px;
    border-radius: 8px;
    overflow: hidden;
}
</style>

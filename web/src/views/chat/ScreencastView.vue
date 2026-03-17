<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from "vue";
import { Maximize2, Minimize2 } from "lucide-vue-next";
import { useUserStore } from "@/stores/modules/user";

const props = defineProps<{
    nodeId: string;
    active: boolean;
}>();

const userStore = useUserStore();
const canvasRef = ref<HTMLCanvasElement>();
const containerRef = ref<HTMLDivElement>();
const fps = ref(0);
const connected = ref(false);
const error = ref("");
const isFullscreen = ref(false);

let ws: WebSocket | null = null;
let frameCount = 0;
let fpsTimer: ReturnType<typeof setInterval> | null = null;

function getWsUrl() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const token = encodeURIComponent(userStore.token);
    return `${proto}//${location.host}/api/admin/remote-nodes/${props.nodeId}/screencast?token=${token}`;
}

function connect() {
    if (ws) disconnect();
    error.value = "";

    ws = new WebSocket(getWsUrl());
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        connected.value = true;
        frameCount = 0;
        fpsTimer = setInterval(() => {
            fps.value = frameCount;
            frameCount = 0;
        }, 1000);
    };

    ws.onmessage = (ev) => {
        if (typeof ev.data === "string") {
            try {
                const msg = JSON.parse(ev.data);
                if (msg.error) {
                    error.value = msg.error;
                    return;
                }
            } catch { /* binary frame fallthrough */ }
        }

        if (ev.data instanceof ArrayBuffer) {
            frameCount++;
            renderFrame(new Uint8Array(ev.data));
        }
    };

    ws.onclose = () => {
        connected.value = false;
        if (fpsTimer) { clearInterval(fpsTimer); fpsTimer = null; }
    };

    ws.onerror = () => {
        error.value = "Screencast 连接失败";
    };
}

let canvasInited = false;

function renderFrame(data: Uint8Array) {
    const canvas = canvasRef.value;
    if (!canvas) return;

    const blob = new Blob([data], { type: "image/jpeg" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
        if (!canvasInited) {
            canvas.width = img.width;
            canvas.height = img.height;
            canvasInited = true;
        }
        const ctx = canvas.getContext("2d");
        ctx?.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
    };
    img.src = url;
}

function disconnect() {
    if (fpsTimer) { clearInterval(fpsTimer); fpsTimer = null; }
    ws?.close();
    ws = null;
    connected.value = false;
    fps.value = 0;
    canvasInited = false;
}

function toggleFullscreen() {
    const el = containerRef.value;
    if (!el) return;
    if (!document.fullscreenElement) {
        el.requestFullscreen().then(() => { isFullscreen.value = true; });
    } else {
        document.exitFullscreen().then(() => { isFullscreen.value = false; });
    }
}

watch(() => props.active, (val) => {
    if (val) connect();
    else disconnect();
}, { immediate: true });

onBeforeUnmount(disconnect);

document.addEventListener("fullscreenchange", () => {
    isFullscreen.value = !!document.fullscreenElement;
});
</script>

<template>
    <div ref="containerRef" class="relative bg-black rounded-lg overflow-hidden" :class="{ 'aspect-video': !isFullscreen }">
        <canvas
            ref="canvasRef"
            class="absolute inset-0 w-full h-full object-contain"
        />

        <div v-if="error" class="absolute inset-0 flex items-center justify-center bg-black/60">
            <span class="text-red-400 text-xs">{{ error }}</span>
        </div>

        <div v-if="!connected && !error && active" class="absolute inset-0 flex items-center justify-center bg-black/60">
            <span class="text-gray-400 text-xs">正在连接浏览器画面...</span>
        </div>

        <div class="absolute bottom-2 right-2 flex items-center gap-2">
            <span v-if="connected" class="text-[10px] text-white/60 bg-black/40 px-1.5 py-0.5 rounded">
                {{ fps }} FPS
            </span>
            <button
                @click="toggleFullscreen"
                class="text-white/60 hover:text-white bg-black/40 p-1 rounded transition-colors"
            >
                <Minimize2 v-if="isFullscreen" :size="14" />
                <Maximize2 v-else :size="14" />
            </button>
        </div>
    </div>
</template>

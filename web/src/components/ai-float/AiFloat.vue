<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import { X } from "lucide-vue-next";
import AiIcon from "./AiIcon.vue";
import ChatView from "@/views/chat/Index.vue";
import { useAiFloat } from "@/composables/useAiFloat";

const route = useRoute();
const { pendingPrompt, consumePrompt } = useAiFloat();

const panelOpen = ref(false);
const expanded = ref(false);
const showContacts = ref(false);
const sessionId = ref(localStorage.getItem("ai-float-session-id") || "");
const chatRef = ref<InstanceType<typeof ChatView> | null>(null);

const isOnChatPage = computed(() => route.path === "/chat");

const BTN_SIZE = 44;
const EDGE_MARGIN = 12;
const SNAP_MARGIN = 24;
const POS_KEY = "ai-float-corner";

type Corner = "br" | "bl" | "tr" | "tl";
const CORNERS: Corner[] = ["br", "bl", "tr", "tl"];

const currentCorner = ref<Corner>("br");
const pos = ref({ right: SNAP_MARGIN, bottom: SNAP_MARGIN });
const dragging = ref(false);
const snapping = ref(false);
const hasMoved = ref(false);
let dragOrigin = { x: 0, y: 0, right: 0, bottom: 0 };

function cornerToPos(c: Corner): { right: number; bottom: number } {
    const w = window.innerWidth;
    const h = window.innerHeight;
    switch (c) {
        case "br": return { right: SNAP_MARGIN, bottom: SNAP_MARGIN };
        case "bl": return { right: w - BTN_SIZE - SNAP_MARGIN, bottom: SNAP_MARGIN };
        case "tr": return { right: SNAP_MARGIN, bottom: h - BTN_SIZE - SNAP_MARGIN };
        case "tl": return { right: w - BTN_SIZE - SNAP_MARGIN, bottom: h - BTN_SIZE - SNAP_MARGIN };
    }
}

function nearestCorner(p: { right: number; bottom: number }): Corner {
    let best: Corner = "br";
    let bestDist = Infinity;
    for (const c of CORNERS) {
        const cp = cornerToPos(c);
        const d = Math.hypot(p.right - cp.right, p.bottom - cp.bottom);
        if (d < bestDist) { bestDist = d; best = c; }
    }
    return best;
}

function clampPos(p: { right: number; bottom: number }) {
    return {
        right: Math.max(EDGE_MARGIN, Math.min(window.innerWidth - BTN_SIZE - EDGE_MARGIN, p.right)),
        bottom: Math.max(EDGE_MARGIN, Math.min(window.innerHeight - BTN_SIZE - EDGE_MARGIN, p.bottom)),
    };
}

function syncPosToCorner() {
    pos.value = cornerToPos(currentCorner.value);
}

function onDragStart(e: PointerEvent) {
    snapping.value = false;
    dragging.value = true;
    hasMoved.value = false;
    dragOrigin = { x: e.clientX, y: e.clientY, right: pos.value.right, bottom: pos.value.bottom };
    document.addEventListener("pointermove", onDragMove);
    document.addEventListener("pointerup", onDragEnd);
}

function onDragMove(e: PointerEvent) {
    const dx = e.clientX - dragOrigin.x;
    const dy = e.clientY - dragOrigin.y;
    if (!hasMoved.value && Math.abs(dx) + Math.abs(dy) < 5) return;
    if (!hasMoved.value) {
        hasMoved.value = true;
        panelOpen.value = false;
    }
    pos.value = clampPos({ right: dragOrigin.right - dx, bottom: dragOrigin.bottom - dy });
}

function onDragEnd() {
    document.removeEventListener("pointermove", onDragMove);
    document.removeEventListener("pointerup", onDragEnd);
    dragging.value = false;
    if (hasMoved.value) {
        const corner = nearestCorner(pos.value);
        currentCorner.value = corner;
        snapping.value = true;
        pos.value = cornerToPos(corner);
        localStorage.setItem(POS_KEY, corner);
        setTimeout(() => { snapping.value = false; }, 350);
    }
}

const containerStyle = computed(() => ({
    right: pos.value.right + "px",
    bottom: pos.value.bottom + "px",
}));

const isTopCorner = computed(() => currentCorner.value === "tr" || currentCorner.value === "tl");

const panelStyle = computed(() => {
    if (expanded.value) {
        return {
            position: "fixed" as const,
            right: "0",
            top: "0",
            bottom: "0",
            left: "auto",
            width: "50vw",
            height: "100vh",
            borderRadius: "0",
        };
    }
    const style: Record<string, string> = {
        width: showContacts.value ? "660px" : "420px",
    };
    if (currentCorner.value === "br" || currentCorner.value === "tr") {
        style.right = "0";
        style.left = "auto";
    } else {
        style.left = "0";
        style.right = "auto";
    }
    return style;
});

onMounted(() => {
    const saved = localStorage.getItem(POS_KEY);
    if (saved && CORNERS.includes(saved as Corner)) {
        currentCorner.value = saved as Corner;
    }
    syncPosToCorner();
    window.addEventListener("resize", syncPosToCorner);
});

onBeforeUnmount(() => {
    window.removeEventListener("resize", syncPosToCorner);
});

function togglePanel() { panelOpen.value = !panelOpen.value; }

function handleBtnClick() {
    if (hasMoved.value) {
        hasMoved.value = false;
        return;
    }
    togglePanel();
}

function toggleExpand() {
    expanded.value = !expanded.value;
}

watch(() => (chatRef.value?.currentSessionId as unknown as string), (val) => {
    if (val) {
        sessionId.value = val;
        localStorage.setItem("ai-float-session-id", val);
    }
});

watch(panelOpen, (open) => {
    if (open) nextTick(() => chatRef.value);
});

watch(pendingPrompt, (prompt) => {
    if (!prompt) return;
    const text = consumePrompt();
    panelOpen.value = true;
    nextTick(() => {
        chatRef.value?.fillPrompt(text);
    });
});
</script>

<template>
    <Teleport to="body">
    <div v-if="!isOnChatPage" class="ai-float-container" :class="{ 'ai-float-snapping': snapping }" :style="containerStyle">
        <transition name="ai-float-panel" type="animation">
            <div v-if="panelOpen" class="ai-float-panel" :class="{ 'ai-float-panel-top': isTopCorner && !expanded, 'ai-float-panel-expanded': expanded }" :style="panelStyle">
                <div class="ai-float-body">
                    <ChatView
                        ref="chatRef"
                        embedded
                        :embedded-expanded="expanded"
                        :initial-session-id="sessionId"
                        :embedded-sidebar="showContacts"
                        @embedded-maximize="toggleExpand"
                        @embedded-close="panelOpen = false; expanded = false"
                        @embedded-toggle-sidebar="showContacts = !showContacts"
                    />
                </div>
            </div>
        </transition>

        <!-- Floating Button -->
        <button
            v-if="!expanded"
            class="ai-float-btn"
            :class="{ 'ai-float-btn-active': panelOpen, 'ai-float-btn-dragging': dragging }"
            @pointerdown="onDragStart"
            @click="handleBtnClick"
        >
            <transition name="ai-float-icon" mode="out-in">
                <X v-if="panelOpen" :size="18" class="text-white" key="close" />
                <AiIcon v-else key="ai" :size="38" :animated="true" />
            </transition>
        </button>
    </div>
    </Teleport>
</template>

<style scoped>
.ai-float-container {
    position: fixed;
    z-index: 2000;
}
.ai-float-snapping {
    transition: right 0.3s cubic-bezier(0.25, 1, 0.5, 1), bottom 0.3s cubic-bezier(0.25, 1, 0.5, 1);
}

.ai-float-btn {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: transparent;
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.3), 0 0 30px rgba(139, 92, 246, 0.12);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    border: none;
    touch-action: none;
    user-select: none;
    transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
    position: relative;
    overflow: visible;
}
.ai-float-btn::before {
    content: "";
    position: absolute;
    inset: -2px;
    border-radius: 50%;
    background: conic-gradient(
        from 0deg,
        transparent 0%,
        rgba(120, 217, 255, 0.35) 15%,
        transparent 30%,
        rgba(139, 92, 246, 0.4) 50%,
        transparent 65%,
        rgba(67, 209, 250, 0.3) 80%,
        transparent 100%
    );
    animation: ai-border-spin 4s linear infinite;
    z-index: -1;
    mask: radial-gradient(circle, transparent 48%, black 52%);
    -webkit-mask: radial-gradient(circle, transparent 48%, black 52%);
}
.ai-float-btn::after {
    content: "";
    position: absolute;
    inset: -4px;
    border-radius: 50%;
    border: 1.5px solid rgba(120, 217, 255, 0.15);
    animation: ai-pulse-ring 3.5s ease-out infinite;
    pointer-events: none;
}
.ai-float-btn:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 28px rgba(99, 102, 241, 0.4), 0 0 40px rgba(120, 217, 255, 0.15);
}
.ai-float-btn:active { transform: scale(0.93); }
.ai-float-btn-active {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, #6366f1, #7c3aed);
}
.ai-float-btn-active::before,
.ai-float-btn-active::after { display: none; }
.ai-float-btn-dragging {
    cursor: grabbing !important;
    transition: none !important;
}

@keyframes ai-border-spin {
    to { transform: rotate(360deg); }
}
@keyframes ai-pulse-ring {
    0% { transform: scale(1); opacity: 0.4; }
    70% { transform: scale(1.3); opacity: 0; }
    100% { transform: scale(1.3); opacity: 0; }
}

.ai-float-panel {
    position: absolute;
    bottom: 56px;
    height: 600px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1), 0 2px 10px rgba(0, 0, 0, 0.06);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: width 0.3s ease, height 0.3s ease, border-radius 0.3s ease;
}
.ai-float-panel-top {
    bottom: auto;
    top: 56px;
}
.ai-float-panel-expanded {
    bottom: 0 !important;
    top: 0 !important;
    box-shadow: -4px 0 24px rgba(0, 0, 0, 0.1);
}

.ai-float-body {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}
.ai-float-body :deep(> .flex.h-full) {
    height: 100%;
}

/* Compact ContactList in embedded */
.ai-float-body :deep(.border-r .mx-2) {
    margin-left: 2px;
    margin-right: 2px;
}
.ai-float-body :deep(.border-r .px-3.py-3) {
    padding: 8px 8px;
}
.ai-float-body :deep(.border-r .gap-3) {
    gap: 8px;
}
.ai-float-body :deep(.border-r .w-10.h-10) {
    width: 32px;
    height: 32px;
}

/* Transitions */
.ai-float-panel-enter-active { animation: ai-panel-in 0.25s ease-out; }
.ai-float-panel-leave-active { animation: ai-panel-out 0.2s ease-in; }
@keyframes ai-panel-in {
    from { opacity: 0; transform: translateY(12px) scale(0.95); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes ai-panel-out {
    from { opacity: 1; transform: translateY(0) scale(1); }
    to { opacity: 0; transform: translateY(12px) scale(0.95); }
}
.ai-float-icon-enter-active,
.ai-float-icon-leave-active {
    transition: transform 0.2s ease, opacity 0.2s ease;
}
.ai-float-icon-enter-from { transform: rotate(-90deg) scale(0.5); opacity: 0; }
.ai-float-icon-leave-to { transform: rotate(90deg) scale(0.5); opacity: 0; }
</style>

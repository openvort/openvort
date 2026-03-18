<script setup lang="ts">
import { ref, computed, watch, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import { X } from "lucide-vue-next";
import AiIcon from "./AiIcon.vue";
import ChatView from "@/views/chat/Index.vue";
import { useAiFloat } from "@/composables/useAiFloat";

const route = useRoute();
const router = useRouter();
const { pendingPrompt, consumePrompt } = useAiFloat();

const panelOpen = ref(false);
const showContacts = ref(false);
const sessionId = ref(localStorage.getItem("ai-float-session-id") || "");
const chatRef = ref<InstanceType<typeof ChatView> | null>(null);

const isOnChatPage = computed(() => route.path === "/chat");

function togglePanel() { panelOpen.value = !panelOpen.value; }

function goToFullChat() {
    const draft = (chatRef.value?.inputText as unknown as string) ?? "";
    const sid = (chatRef.value?.currentSessionId as unknown as string) || sessionId.value;
    panelOpen.value = false;
    if (sid) localStorage.setItem("chat-last-session-id", sid);
    if (draft) localStorage.setItem("ai-float-draft", draft);
    router.push("/chat");
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
    <div v-if="!isOnChatPage" class="ai-float-container">
        <transition name="ai-float-panel" type="animation">
            <div v-if="panelOpen" class="ai-float-panel" :style="{ width: showContacts ? '660px' : '420px' }">
                <div class="ai-float-body">
                    <ChatView
                        ref="chatRef"
                        embedded
                        :initial-session-id="sessionId"
                        :embedded-sidebar="showContacts"
                        @embedded-maximize="goToFullChat"
                        @embedded-close="panelOpen = false"
                        @embedded-toggle-sidebar="showContacts = !showContacts"
                    />
                </div>
            </div>
        </transition>

        <!-- Floating Button -->
        <button
            class="ai-float-btn"
            :class="{ 'ai-float-btn-active': panelOpen }"
            @click="togglePanel"
        >
            <transition name="ai-float-icon" mode="out-in">
                <X v-if="panelOpen" :size="18" class="text-white" key="close" />
                <AiIcon v-else key="ai" :size="20" :animated="true" class="text-white" />
            </transition>
        </button>
    </div>
</template>

<style scoped>
.ai-float-container {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 1000;
}

.ai-float-btn {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7, #d946ef);
    background-size: 200% 200%;
    animation: ai-float-gradient 4s ease infinite;
    box-shadow: 0 3px 14px rgba(139, 92, 246, 0.35), 0 1px 6px rgba(139, 92, 246, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    border: none;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    position: relative;
    overflow: visible;
}
/* Spinning conic border */
.ai-float-btn::before {
    content: "";
    position: absolute;
    inset: -2px;
    border-radius: 50%;
    background: conic-gradient(
        from 0deg,
        transparent 0%,
        rgba(139, 92, 246, 0.45) 20%,
        transparent 40%,
        rgba(168, 85, 247, 0.3) 60%,
        transparent 80%,
        rgba(99, 102, 241, 0.45) 95%,
        transparent 100%
    );
    animation: ai-border-spin 3s linear infinite;
    z-index: -1;
    mask: radial-gradient(circle, transparent 45%, black 50%);
    -webkit-mask: radial-gradient(circle, transparent 45%, black 50%);
}
/* Pulse ring */
.ai-float-btn::after {
    content: "";
    position: absolute;
    inset: -3px;
    border-radius: 50%;
    border: 1.5px solid rgba(139, 92, 246, 0.2);
    animation: ai-pulse-ring 3s ease-out infinite;
    pointer-events: none;
}
.ai-float-btn:hover {
    transform: scale(1.08);
    box-shadow: 0 4px 18px rgba(139, 92, 246, 0.4), 0 2px 8px rgba(139, 92, 246, 0.2);
}
.ai-float-btn:active { transform: scale(0.95); }
.ai-float-btn-active {
    background: linear-gradient(135deg, #6366f1, #7c3aed);
    animation: none;
}
.ai-float-btn-active::before,
.ai-float-btn-active::after { display: none; }

@keyframes ai-float-gradient {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
}
@keyframes ai-border-spin {
    to { transform: rotate(360deg); }
}
@keyframes ai-pulse-ring {
    0% { transform: scale(1); opacity: 0.45; }
    70% { transform: scale(1.25); opacity: 0; }
    100% { transform: scale(1.25); opacity: 0; }
}

.ai-float-panel {
    position: absolute;
    bottom: 52px;
    right: 0;
    height: 600px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1), 0 2px 10px rgba(0, 0, 0, 0.06);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: width 0.25s ease;
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

<script setup lang="ts">
import { useRouter } from "vue-router";
import { MessageSquare, ArrowRight } from "lucide-vue-next";

const router = useRouter();

defineProps<{
    messages: { user: string; content: string; time: string }[];
}>();

const AVATAR_COLORS = [
    "bg-blue-500", "bg-emerald-500", "bg-purple-500", "bg-amber-500",
    "bg-rose-500", "bg-cyan-500", "bg-indigo-500", "bg-teal-500",
];

function getInitial(name: string): string {
    if (!name) return "?";
    const first = name.trim().charAt(0);
    return /[a-zA-Z]/.test(first) ? first.toUpperCase() : first;
}

function getColor(name: string): string {
    if (!name) return AVATAR_COLORS[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}
</script>

<template>
    <vort-card :shadow="false" title="最近对话">
        <template #extra>
            <a class="text-xs text-blue-600 cursor-pointer flex items-center gap-0.5 hover:text-blue-700" @click="router.push('/chat')">
                全部对话 <ArrowRight :size="12" />
            </a>
        </template>
        <div v-if="messages.length === 0" class="flex flex-col items-center justify-center py-12 text-center">
            <div class="w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center mb-4">
                <MessageSquare :size="24" class="text-blue-400" />
            </div>
            <p class="text-sm text-gray-500 mb-1">暂无对话记录</p>
            <p class="text-xs text-gray-400 mb-4">开始和 AI 助手对话，记录将在这里展示</p>
            <VortButton size="small" variant="primary" @click="router.push('/chat')">
                <MessageSquare :size="12" class="mr-1" /> 开始对话
            </VortButton>
        </div>
        <div v-else class="space-y-1">
            <div
                v-for="(msg, i) in messages" :key="i"
                class="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                @click="router.push('/chat')"
            >
                <span
                    class="inline-flex items-center justify-center w-8 h-8 rounded-full text-white text-xs font-medium flex-shrink-0"
                    :class="getColor(msg.user)"
                >{{ getInitial(msg.user) }}</span>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between">
                        <span class="text-sm font-medium text-gray-700">{{ msg.user }}</span>
                        <span class="text-xs text-gray-400 flex-shrink-0 ml-2">{{ msg.time }}</span>
                    </div>
                    <p class="text-sm text-gray-500 truncate mt-0.5">{{ msg.content }}</p>
                </div>
            </div>
        </div>
    </vort-card>
</template>

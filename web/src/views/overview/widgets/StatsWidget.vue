<script setup lang="ts">
import { Activity, MessageSquare, ArrowUpRight, Zap, Puzzle, Radio } from "lucide-vue-next";

const props = defineProps<{
    data: {
        agentStatus: string;
        totalMessages: number;
        totalInputTokens: number;
        totalOutputTokens: number;
        totalPlugins?: number;
        totalChannels?: number;
    };
}>();

function formatTokens(n: number): string {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return String(n);
}

const cards = [
    { key: "agentStatus", label: "Agent 状态", icon: Activity, gradient: "from-green-500 to-emerald-600", bgClass: "bg-green-50" },
    { key: "totalMessages", label: "消息总数", icon: MessageSquare, gradient: "from-blue-500 to-blue-600", bgClass: "bg-blue-50" },
    { key: "totalInputTokens", label: "Input Tokens", icon: ArrowUpRight, gradient: "from-amber-500 to-orange-500", bgClass: "bg-amber-50" },
    { key: "totalOutputTokens", label: "Output Tokens", icon: Zap, gradient: "from-purple-500 to-violet-600", bgClass: "bg-purple-50" },
    { key: "totalPlugins", label: "已加载插件", icon: Puzzle, gradient: "from-rose-500 to-pink-600", bgClass: "bg-rose-50" },
    { key: "totalChannels", label: "通道数", icon: Radio, gradient: "from-cyan-500 to-teal-600", bgClass: "bg-cyan-50" },
];
</script>

<template>
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div
            v-for="card in cards"
            :key="card.key"
            class="bg-white rounded-xl border border-gray-100 p-4 hover:shadow-sm transition-shadow"
        >
            <div class="flex items-center justify-between mb-3">
                <p class="text-xs text-gray-500 font-medium">{{ card.label }}</p>
                <div
                    class="w-8 h-8 rounded-lg flex items-center justify-center bg-gradient-to-br shadow-sm"
                    :class="card.gradient"
                >
                    <component :is="card.icon" :size="16" class="text-white" />
                </div>
            </div>
            <div v-if="card.key === 'agentStatus'">
                <p class="text-xl font-bold"
                    :class="props.data.agentStatus === 'running' ? 'text-green-600' : 'text-red-600'">
                    {{ props.data.agentStatus === 'running' ? '运行中' : '已停止' }}
                </p>
                <div class="flex items-center gap-1 mt-1">
                    <span class="w-1.5 h-1.5 rounded-full" :class="props.data.agentStatus === 'running' ? 'bg-green-500 animate-pulse' : 'bg-red-500'" />
                    <span class="text-xs text-gray-400">{{ props.data.agentStatus === 'running' ? '服务正常' : '已停止运行' }}</span>
                </div>
            </div>
            <div v-else-if="card.key === 'totalMessages'">
                <p class="text-xl font-bold text-gray-800">{{ props.data.totalMessages }}</p>
                <span class="text-xs text-gray-400 mt-1 block">累计对话消息</span>
            </div>
            <div v-else-if="card.key === 'totalInputTokens'">
                <p class="text-xl font-bold text-gray-800">{{ formatTokens(props.data.totalInputTokens) }}</p>
                <span class="text-xs text-gray-400 mt-1 block">输入 Token 用量</span>
            </div>
            <div v-else-if="card.key === 'totalOutputTokens'">
                <p class="text-xl font-bold text-gray-800">{{ formatTokens(props.data.totalOutputTokens) }}</p>
                <span class="text-xs text-gray-400 mt-1 block">输出 Token 用量</span>
            </div>
            <div v-else-if="card.key === 'totalPlugins'">
                <p class="text-xl font-bold text-gray-800">{{ props.data.totalPlugins ?? 0 }}</p>
                <span class="text-xs text-gray-400 mt-1 block">插件已就绪</span>
            </div>
            <div v-else-if="card.key === 'totalChannels'">
                <p class="text-xl font-bold text-gray-800">{{ props.data.totalChannels ?? 0 }}</p>
                <span class="text-xs text-gray-400 mt-1 block">通道已连接</span>
            </div>
        </div>
    </div>
</template>

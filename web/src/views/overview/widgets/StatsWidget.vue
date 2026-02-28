<script setup lang="ts">
import { Activity, MessageSquare, ArrowUpRight, Zap } from "lucide-vue-next";

const props = defineProps<{
    data: {
        agentStatus: string;
        totalMessages: number;
        totalInputTokens: number;
        totalOutputTokens: number;
    };
}>();

function formatTokens(n: number): string {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return String(n);
}

const cards = [
    { key: "agentStatus", label: "Agent 状态", icon: Activity, bgClass: "bg-green-50", iconClass: "text-green-600" },
    { key: "totalMessages", label: "消息总数", icon: MessageSquare, bgClass: "bg-blue-50", iconClass: "text-blue-600" },
    { key: "totalInputTokens", label: "Input Tokens", icon: ArrowUpRight, bgClass: "bg-amber-50", iconClass: "text-amber-600" },
    { key: "totalOutputTokens", label: "Output Tokens", icon: Zap, bgClass: "bg-purple-50", iconClass: "text-purple-600" },
];
</script>

<template>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <vort-card v-for="card in cards" :key="card.key" :shadow="false" padding="small">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-sm text-gray-500">{{ card.label }}</p>
                    <p v-if="card.key === 'agentStatus'" class="text-2xl font-semibold mt-1"
                        :class="props.data.agentStatus === 'running' ? 'text-green-600' : 'text-red-600'">
                        {{ props.data.agentStatus === 'running' ? '运行中' : '已停止' }}
                    </p>
                    <p v-else-if="card.key === 'totalMessages'" class="text-2xl font-semibold mt-1 text-blue-600">
                        {{ props.data.totalMessages }}
                    </p>
                    <p v-else-if="card.key === 'totalInputTokens'" class="text-2xl font-semibold mt-1 text-amber-600">
                        {{ formatTokens(props.data.totalInputTokens) }}
                    </p>
                    <p v-else class="text-2xl font-semibold mt-1 text-purple-600">
                        {{ formatTokens(props.data.totalOutputTokens) }}
                    </p>
                </div>
                <div class="w-12 h-12 rounded-full flex items-center justify-center" :class="card.bgClass">
                    <component :is="card.icon" :size="24" :class="card.iconClass" />
                </div>
            </div>
        </vort-card>
    </div>
</template>

<script setup lang="ts">
import { Bot } from "lucide-vue-next";

defineProps<{
    messages: { user: string; content: string; time: string }[];
}>();
</script>

<template>
    <vort-card :shadow="false" title="最近对话">
        <div v-if="messages.length === 0" class="text-center py-8 text-gray-400 text-sm">
            暂无对话记录
        </div>
        <div v-else class="space-y-3">
            <div v-for="(msg, i) in messages" :key="i"
                class="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50">
                <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                    <Bot :size="16" class="text-blue-600" />
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between">
                        <span class="text-sm font-medium text-gray-700">{{ msg.user }}</span>
                        <span class="text-xs text-gray-400">{{ msg.time }}</span>
                    </div>
                    <p class="text-sm text-gray-500 truncate mt-0.5">{{ msg.content }}</p>
                </div>
            </div>
        </div>
    </vort-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getDashboard } from "@/api";
import { Bot, Users, Puzzle, Radio, MessageSquare, Activity } from "lucide-vue-next";

const stats = ref({
    agentStatus: "running",
    totalMessages: 0,
    totalContacts: 0,
    totalPlugins: 0,
    totalChannels: 0,
    recentMessages: [] as { user: string; content: string; time: string }[]
});

onMounted(async () => {
    try {
        const res: any = await getDashboard();
        if (res) Object.assign(stats.value, res);
    } catch { /* 后端未就绪时使用默认值 */ }
});
</script>

<template>
    <div class="space-y-6">
        <h2 class="text-lg font-medium text-gray-800">仪表盘</h2>

        <!-- 统计卡片 -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <vort-card :shadow="false" padding="small">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500">Agent 状态</p>
                        <p class="text-2xl font-semibold mt-1" :class="stats.agentStatus === 'running' ? 'text-green-600' : 'text-red-600'">
                            {{ stats.agentStatus === 'running' ? '运行中' : '已停止' }}
                        </p>
                    </div>
                    <div class="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center">
                        <Activity :size="24" class="text-green-600" />
                    </div>
                </div>
            </vort-card>
            <vort-card :shadow="false" padding="small">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500">消息总数</p>
                        <p class="text-2xl font-semibold mt-1 text-blue-600">{{ stats.totalMessages }}</p>
                    </div>
                    <div class="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center">
                        <MessageSquare :size="24" class="text-blue-600" />
                    </div>
                </div>
            </vort-card>
            <vort-card :shadow="false" padding="small">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500">联系人</p>
                        <p class="text-2xl font-semibold mt-1 text-purple-600">{{ stats.totalContacts }}</p>
                    </div>
                    <div class="w-12 h-12 rounded-full bg-purple-50 flex items-center justify-center">
                        <Users :size="24" class="text-purple-600" />
                    </div>
                </div>
            </vort-card>
            <vort-card :shadow="false" padding="small">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500">已加载插件</p>
                        <p class="text-2xl font-semibold mt-1 text-orange-600">{{ stats.totalPlugins }}</p>
                    </div>
                    <div class="w-12 h-12 rounded-full bg-orange-50 flex items-center justify-center">
                        <Puzzle :size="24" class="text-orange-600" />
                    </div>
                </div>
            </vort-card>
        </div>

        <!-- 最近消息 -->
        <vort-card :shadow="false" title="最近对话">
            <div v-if="stats.recentMessages.length === 0" class="text-center py-8 text-gray-400 text-sm">
                暂无对话记录
            </div>
            <div v-else class="space-y-3">
                <div v-for="(msg, i) in stats.recentMessages" :key="i" class="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50">
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
    </div>
</template>

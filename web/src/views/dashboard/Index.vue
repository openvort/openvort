<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from "vue";
import { getDashboard } from "@/api";
import { Bot, Users, Puzzle, Radio, MessageSquare, Activity, Zap, ArrowUpRight } from "lucide-vue-next";
import * as echarts from "echarts";

const stats = ref({
    agentStatus: "running",
    totalMessages: 0,
    totalContacts: 0,
    totalPlugins: 0,
    totalChannels: 0,
    totalInputTokens: 0,
    totalOutputTokens: 0,
    sessionUsage: [] as { key: string; user_id: string; channel: string; input_tokens: number; output_tokens: number; messages: number }[],
    recentMessages: [] as { user: string; content: string; time: string }[],
});

const tokenChartRef = ref<HTMLElement>();
const usageChartRef = ref<HTMLElement>();
let tokenChart: echarts.ECharts | null = null;
let usageChart: echarts.ECharts | null = null;

function formatTokens(n: number): string {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return String(n);
}

// __CONTINUE_HERE__

function renderTokenChart() {
    if (!tokenChartRef.value) return;
    if (!tokenChart) tokenChart = echarts.init(tokenChartRef.value);
    tokenChart.setOption({
        tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
        legend: { bottom: 0, textStyle: { fontSize: 12 } },
        color: ["#3b82f6", "#f59e0b"],
        series: [{
            type: "pie",
            radius: ["45%", "70%"],
            center: ["50%", "45%"],
            avoidLabelOverlap: false,
            label: { show: false },
            data: [
                { value: stats.value.totalInputTokens, name: "Input Tokens" },
                { value: stats.value.totalOutputTokens, name: "Output Tokens" },
            ],
        }],
    });
}

function renderUsageChart() {
    if (!usageChartRef.value || !stats.value.sessionUsage.length) return;
    if (!usageChart) usageChart = echarts.init(usageChartRef.value);
    const top = stats.value.sessionUsage.slice(0, 10);
    const names = top.map(s => s.user_id || s.key).reverse();
    const input = top.map(s => s.input_tokens).reverse();
    const output = top.map(s => s.output_tokens).reverse();
    usageChart.setOption({
        tooltip: { trigger: "axis" },
        legend: { bottom: 0, textStyle: { fontSize: 12 } },
        grid: { left: 80, right: 20, top: 10, bottom: 40 },
        xAxis: { type: "value" },
        yAxis: { type: "category", data: names, axisLabel: { fontSize: 11 } },
        color: ["#3b82f6", "#f59e0b"],
        series: [
            { name: "Input", type: "bar", stack: "total", data: input, barWidth: 16 },
            { name: "Output", type: "bar", stack: "total", data: output, barWidth: 16 },
        ],
    });
}

function handleResize() {
    tokenChart?.resize();
    usageChart?.resize();
}

onMounted(async () => {
    try {
        const res: any = await getDashboard();
        if (res) Object.assign(stats.value, res);
    } catch { /* 后端未就绪时使用默认值 */ }
    await nextTick();
    renderTokenChart();
    renderUsageChart();
    window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
    window.removeEventListener("resize", handleResize);
    tokenChart?.dispose();
    usageChart?.dispose();
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
                        <p class="text-sm text-gray-500">Input Tokens</p>
                        <p class="text-2xl font-semibold mt-1 text-amber-600">{{ formatTokens(stats.totalInputTokens) }}</p>
                    </div>
                    <div class="w-12 h-12 rounded-full bg-amber-50 flex items-center justify-center">
                        <ArrowUpRight :size="24" class="text-amber-600" />
                    </div>
                </div>
            </vort-card>
            <vort-card :shadow="false" padding="small">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500">Output Tokens</p>
                        <p class="text-2xl font-semibold mt-1 text-purple-600">{{ formatTokens(stats.totalOutputTokens) }}</p>
                    </div>
                    <div class="w-12 h-12 rounded-full bg-purple-50 flex items-center justify-center">
                        <Zap :size="24" class="text-purple-600" />
                    </div>
                </div>
            </vort-card>
        </div>

        <!-- 图表区域 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <vort-card :shadow="false" title="Token 用量分布">
                <div ref="tokenChartRef" class="w-full h-[280px]" />
                <div v-if="!stats.totalInputTokens && !stats.totalOutputTokens" class="absolute inset-0 flex items-center justify-center text-gray-400 text-sm">
                    暂无用量数据
                </div>
            </vort-card>
            <vort-card :shadow="false" title="会话用量 Top 10">
                <div ref="usageChartRef" class="w-full h-[280px]" />
                <div v-if="!stats.sessionUsage.length" class="absolute inset-0 flex items-center justify-center text-gray-400 text-sm">
                    暂无会话数据
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

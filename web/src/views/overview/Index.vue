<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Settings2 } from "lucide-vue-next";
import { getDashboard } from "@/api";

import StatsWidget from "./widgets/StatsWidget.vue";
import TokenChartWidget from "./widgets/TokenChartWidget.vue";
import UsageChartWidget from "./widgets/UsageChartWidget.vue";
import RecentChatsWidget from "./widgets/RecentChatsWidget.vue";
import ShortcutsWidget from "./widgets/ShortcutsWidget.vue";
import WidgetCustomize from "./WidgetCustomize.vue";
import type { WidgetConfig } from "./WidgetCustomize.vue";

// ---- 数据 ----

const stats = ref({
    agentStatus: "running",
    totalMessages: 0,
    totalContacts: 0,
    totalPlugins: 0,
    totalChannels: 0,
    totalInputTokens: 0,
    totalOutputTokens: 0,
    sessionUsage: [] as any[],
    recentMessages: [] as { user: string; content: string; time: string }[],
});

onMounted(async () => {
    try {
        const res: any = await getDashboard();
        if (res) Object.assign(stats.value, res);
    } catch { /* 后端未就绪时使用默认值 */ }
});

// ---- Widget 系统 ----

const STORAGE_KEY = "openvort_overview_widgets";

const defaultWidgets: WidgetConfig[] = [
    { id: "shortcuts", title: "快捷入口", description: "常用功能快速跳转", visible: true, span: "full" },
    { id: "stats", title: "统计卡片", description: "Agent 状态、消息数、Token 用量", visible: true, span: "full" },
    { id: "tokenChart", title: "Token 用量分布", description: "Input/Output Token 饼图", visible: true, span: "half" },
    { id: "usageChart", title: "会话用量 Top 10", description: "按会话统计的 Token 用量", visible: true, span: "half" },
    { id: "recentChats", title: "最近对话", description: "最近的对话记录", visible: true, span: "full" },
];

function loadWidgets(): WidgetConfig[] {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
            const saved: WidgetConfig[] = JSON.parse(raw);
            // 合并：保留已保存的顺序和配置，补充新增的 widget
            const knownIds = new Set(saved.map(w => w.id));
            const merged = [...saved];
            for (const dw of defaultWidgets) {
                if (!knownIds.has(dw.id)) merged.push({ ...dw });
            }
            // 移除已删除的 widget
            const validIds = new Set(defaultWidgets.map(w => w.id));
            return merged.filter(w => validIds.has(w.id));
        }
    } catch { /* ignore */ }
    return JSON.parse(JSON.stringify(defaultWidgets));
}

const widgets = ref<WidgetConfig[]>(loadWidgets());

const visibleWidgets = computed(() => widgets.value.filter(w => w.visible));

const customizeOpen = ref(false);

function handleSaveWidgets(updated: WidgetConfig[]) {
    widgets.value = updated;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
}

// widget id → 组件映射
const widgetComponents: Record<string, any> = {
    shortcuts: ShortcutsWidget,
    stats: StatsWidget,
    tokenChart: TokenChartWidget,
    usageChart: UsageChartWidget,
    recentChats: RecentChatsWidget,
};
</script>

<template>
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <h2 class="text-lg font-medium text-gray-800">概览</h2>
            <VortButton variant="text" size="small" @click="customizeOpen = true">
                <Settings2 :size="16" class="mr-1" /> 自定义
            </VortButton>
        </div>

        <!-- Widget 渲染区域 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <template v-for="widget in visibleWidgets" :key="widget.id">
                <div :class="widget.span === 'full' ? 'lg:col-span-2' : ''">
                    <!-- shortcuts -->
                    <ShortcutsWidget v-if="widget.id === 'shortcuts'" />
                    <!-- stats -->
                    <StatsWidget v-else-if="widget.id === 'stats'" :data="stats" />
                    <!-- tokenChart -->
                    <TokenChartWidget v-else-if="widget.id === 'tokenChart'"
                        :input-tokens="stats.totalInputTokens"
                        :output-tokens="stats.totalOutputTokens" />
                    <!-- usageChart -->
                    <UsageChartWidget v-else-if="widget.id === 'usageChart'"
                        :session-usage="stats.sessionUsage" />
                    <!-- recentChats -->
                    <RecentChatsWidget v-else-if="widget.id === 'recentChats'"
                        :messages="stats.recentMessages" />
                </div>
            </template>
        </div>

        <!-- 自定义抽屉 -->
        <WidgetCustomize
            :open="customizeOpen"
            :widgets="widgets"
            @update:open="customizeOpen = $event"
            @save="handleSaveWidgets"
        />
    </div>
</template>

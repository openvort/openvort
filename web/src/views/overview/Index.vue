<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Settings2 } from "lucide-vue-next";
import { useRouter } from "vue-router";
import { getDashboard } from "@/api";

import StatsWidget from "./widgets/StatsWidget.vue";
import TokenChartWidget from "./widgets/TokenChartWidget.vue";
import UsageChartWidget from "./widgets/UsageChartWidget.vue";
import RecentChatsWidget from "./widgets/RecentChatsWidget.vue";
import ShortcutsWidget from "./widgets/ShortcutsWidget.vue";
import ProjectSummaryWidget from "./widgets/ProjectSummaryWidget.vue";
import SystemInfoWidget from "./widgets/SystemInfoWidget.vue";
import WidgetCustomize from "./WidgetCustomize.vue";
import type { WidgetConfig } from "./WidgetCustomize.vue";

const router = useRouter();

// ---- 数据 ----

const llmConfigured = ref(true);

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
    activeSessions: 0,
});

onMounted(async () => {
    try {
        const res: any = await getDashboard();
        if (res) {
            Object.assign(stats.value, res);
            if (res.llmConfigured === false) llmConfigured.value = false;
        }
    } catch { /* fallback to defaults */ }
});

// ---- Widget 系统 ----

const STORAGE_KEY = "openvort_overview_widgets";

const defaultWidgets: WidgetConfig[] = [
    { id: "shortcuts", title: "快捷入口", description: "常用功能快速跳转", visible: true, span: "full" },
    { id: "stats", title: "统计卡片", description: "Agent 状态、消息数、Token 用量、插件/通道数", visible: true, span: "full" },
    { id: "projectSummary", title: "项目管理概览", description: "VortFlow 需求/任务/缺陷统计与进度", visible: true, span: "full" },
    { id: "tokenChart", title: "Token 用量分布", description: "Input/Output Token 饼图", visible: true, span: "half" },
    { id: "usageChart", title: "会话用量 Top 10", description: "按会话统计的 Token 用量", visible: true, span: "half" },
    { id: "recentChats", title: "最近对话", description: "最近的对话记录", visible: true, span: "half" },
    { id: "systemInfo", title: "系统信息", description: "版本、LLM 模型、系统管理入口", visible: true, span: "half" },
];

function loadWidgets(): WidgetConfig[] {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
            const saved: WidgetConfig[] = JSON.parse(raw);
            const knownIds = new Set(saved.map(w => w.id));
            const merged = [...saved];
            for (const dw of defaultWidgets) {
                if (!knownIds.has(dw.id)) merged.push({ ...dw });
            }
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
</script>

<template>
    <div class="space-y-6">
        <VortAlert
            v-if="!llmConfigured"
            type="warning"
            show-icon
            message="AI 功能未配置"
            description="尚未设置 LLM API Key，AI 对话等功能暂不可用。"
        >
            <template #action>
                <VortButton type="primary" size="small" @click="router.push('/ai-config')">去配置</VortButton>
            </template>
        </VortAlert>

        <div class="flex items-center justify-between">
            <h2 class="text-lg font-medium text-gray-800">工作台</h2>
            <VortButton variant="text" size="small" @click="customizeOpen = true">
                <Settings2 :size="16" class="mr-1" /> 自定义
            </VortButton>
        </div>

        <!-- Widget 渲染区域 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <template v-for="widget in visibleWidgets" :key="widget.id">
                <div :class="widget.span === 'full' ? 'lg:col-span-2' : ''">
                    <ShortcutsWidget v-if="widget.id === 'shortcuts'" />
                    <StatsWidget v-else-if="widget.id === 'stats'" :data="stats" />
                    <ProjectSummaryWidget v-else-if="widget.id === 'projectSummary'" />
                    <TokenChartWidget v-else-if="widget.id === 'tokenChart'"
                        :input-tokens="stats.totalInputTokens"
                        :output-tokens="stats.totalOutputTokens" />
                    <UsageChartWidget v-else-if="widget.id === 'usageChart'"
                        :session-usage="stats.sessionUsage" />
                    <RecentChatsWidget v-else-if="widget.id === 'recentChats'"
                        :messages="stats.recentMessages" />
                    <SystemInfoWidget v-else-if="widget.id === 'systemInfo'" />
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

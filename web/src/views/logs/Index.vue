<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { getLogs } from "@/api";
import { RefreshCw, Pause, Play, Trash2 } from "lucide-vue-next";

interface LogEntry {
    id: string;
    timestamp: string;
    level: string;
    source: string;
    message: string;
}

const logs = ref<LogEntry[]>([]);
const loading = ref(false);
const keyword = ref("");
const autoRefresh = ref(true);
const refreshInterval = ref(3000);
let timer: ReturnType<typeof setInterval> | null = null;

const levelFilters = ref<Record<string, boolean>>({
    DEBUG: false,
    INFO: true,
    WARNING: true,
    ERROR: true,
});

const levelConfig: Record<string, { color: string; bg: string; border: string }> = {
    DEBUG: { color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200" },
    INFO: { color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200" },
    WARNING: { color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200" },
    ERROR: { color: "text-red-600", bg: "bg-red-50", border: "border-red-200" },
};

const activeLevels = computed(() =>
    Object.entries(levelFilters.value)
        .filter(([, v]) => v)
        .map(([k]) => k)
        .join(",")
);

const filteredLogs = computed(() => {
    let result = logs.value;
    const kw = keyword.value.trim().toLowerCase();
    if (kw) {
        result = result.filter(
            (l) => l.message.toLowerCase().includes(kw) || l.source.toLowerCase().includes(kw)
        );
    }
    return result;
});

const fetchLogs = async () => {
    loading.value = true;
    try {
        const res: any = await getLogs({ page: 1, size: 500, level: activeLevels.value });
        logs.value = res?.logs || [];
    } catch {
        /* ignore */
    } finally {
        loading.value = false;
    }
};

const startAutoRefresh = () => {
    stopAutoRefresh();
    timer = setInterval(fetchLogs, refreshInterval.value);
};

const stopAutoRefresh = () => {
    if (timer) {
        clearInterval(timer);
        timer = null;
    }
};

const toggleAutoRefresh = () => {
    autoRefresh.value = !autoRefresh.value;
    if (autoRefresh.value) {
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }
};

const clearLogs = () => {
    logs.value = [];
};

const toggleLevel = (level: string) => {
    levelFilters.value[level] = !levelFilters.value[level];
    fetchLogs();
};

onMounted(() => {
    fetchLogs();
    startAutoRefresh();
});

onUnmounted(() => {
    stopAutoRefresh();
});
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <!-- Header -->
            <div class="flex items-center justify-between mb-4">
                <div>
                    <h2 class="text-lg font-medium text-gray-800">运行日志</h2>
                    <p class="text-sm text-gray-400 mt-1">系统运行时产生的实时日志，最多保留 500 条。</p>
                </div>
                <div class="flex items-center gap-2">
                    <VortTooltip :title="autoRefresh ? '暂停自动刷新' : '开启自动刷新'">
                        <VortButton size="small" @click="toggleAutoRefresh">
                            <Pause v-if="autoRefresh" :size="14" />
                            <Play v-else :size="14" />
                        </VortButton>
                    </VortTooltip>
                    <VortTooltip title="手动刷新">
                        <VortButton size="small" @click="fetchLogs">
                            <RefreshCw :size="14" :class="{ 'animate-spin': loading }" />
                        </VortButton>
                    </VortTooltip>
                    <VortTooltip title="清空显示">
                        <VortButton size="small" @click="clearLogs">
                            <Trash2 :size="14" />
                        </VortButton>
                    </VortTooltip>
                </div>
            </div>

            <!-- Filters -->
            <div class="flex items-center gap-3 mb-4">
                <VortInput v-model="keyword" placeholder="搜索日志内容..." style="width: 280px" allow-clear />
                <div class="flex items-center gap-2">
                    <button
                        v-for="level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']"
                        :key="level"
                        class="px-2.5 py-1 rounded text-xs font-medium border transition-all cursor-pointer"
                        :class="levelFilters[level]
                            ? `${levelConfig[level].bg} ${levelConfig[level].color} ${levelConfig[level].border}`
                            : 'bg-gray-50 text-gray-400 border-gray-200'"
                        @click="toggleLevel(level)"
                    >
                        {{ level }}
                    </button>
                </div>
                <div v-if="autoRefresh" class="ml-auto flex items-center gap-1.5">
                    <span class="relative flex h-2 w-2">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                    </span>
                    <span class="text-xs text-gray-400">实时</span>
                </div>
            </div>

            <!-- Log Table -->
            <div class="border border-gray-100 rounded-lg overflow-hidden">
                <div class="bg-gray-50 px-4 py-2.5 flex text-xs font-medium text-gray-500 border-b border-gray-100">
                    <div class="w-[160px] flex-shrink-0">时间</div>
                    <div class="w-[80px] flex-shrink-0">级别</div>
                    <div class="w-[180px] flex-shrink-0">来源</div>
                    <div class="flex-1">内容</div>
                </div>
                <div class="max-h-[calc(100vh-320px)] overflow-y-auto">
                    <template v-if="filteredLogs.length">
                        <div
                            v-for="log in filteredLogs"
                            :key="log.id"
                            class="px-4 py-2 flex items-start text-xs border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
                            :class="log.level === 'ERROR' ? 'bg-red-50/30' : log.level === 'WARNING' ? 'bg-amber-50/30' : ''"
                        >
                            <div class="w-[160px] flex-shrink-0 text-gray-400 font-mono">{{ log.timestamp }}</div>
                            <div class="w-[80px] flex-shrink-0">
                                <span
                                    class="inline-block px-1.5 py-0.5 rounded text-[11px] font-medium"
                                    :class="`${levelConfig[log.level]?.bg || 'bg-gray-50'} ${levelConfig[log.level]?.color || 'text-gray-500'}`"
                                >{{ log.level }}</span>
                            </div>
                            <div class="w-[180px] flex-shrink-0 text-gray-400 font-mono truncate" :title="log.source">{{ log.source }}</div>
                            <div class="flex-1 text-gray-700 break-all font-mono whitespace-pre-wrap">{{ log.message }}</div>
                        </div>
                    </template>
                    <div v-else class="py-16 text-center text-gray-400 text-sm">
                        <p>暂无日志</p>
                        <p class="text-xs mt-1">系统运行后日志将自动显示</p>
                    </div>
                </div>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-between mt-3 text-xs text-gray-400">
                <span>共 {{ filteredLogs.length }} 条日志</span>
                <span v-if="keyword">已过滤，原始 {{ logs.length }} 条</span>
            </div>
        </div>
    </div>
</template>

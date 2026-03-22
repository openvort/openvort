<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { getHealthStatus } from "@/api";
import { Heart, Cpu, Globe, Wrench, Shield, ArrowRight } from "lucide-vue-next";

const router = useRouter();

const loading = ref(true);
const health = ref<{
    version?: string;
    llm_healthy?: boolean;
    llm_model?: string;
    llm_error?: string;
}>({});

onMounted(async () => {
    try {
        const res: any = await getHealthStatus();
        if (res) health.value = res;
    } catch { /* ignore */ }
    finally { loading.value = false; }
});

const llmStatusText = computed(() => {
    if (health.value.llm_healthy === true) return "正常";
    if (health.value.llm_healthy === false) return health.value.llm_error || "异常";
    return "-";
});
const llmStatusClass = computed(() => health.value.llm_healthy === true ? "text-green-600" : health.value.llm_healthy === false ? "text-red-500" : "text-gray-400");
</script>

<template>
    <vort-card :shadow="false" title="系统信息">
        <template #extra>
            <a class="text-xs text-blue-600 cursor-pointer flex items-center gap-0.5 hover:text-blue-700" @click="router.push('/admin/settings')">
                系统设置 <ArrowRight :size="12" />
            </a>
        </template>
        <VortSpin :spinning="loading">
            <div class="space-y-3">
                <div class="flex items-center gap-3 p-3 rounded-lg bg-gray-50/60">
                    <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-rose-50">
                        <Heart :size="16" class="text-rose-500" />
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs text-gray-400">系统版本</p>
                        <p class="text-sm font-medium text-gray-800 truncate mt-0.5">{{ health.version || '-' }}</p>
                    </div>
                </div>
                <div class="flex items-center gap-3 p-3 rounded-lg bg-gray-50/60">
                    <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-blue-50">
                        <Cpu :size="16" class="text-blue-500" />
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs text-gray-400">LLM 模型</p>
                        <p class="text-sm font-medium text-gray-800 truncate mt-0.5">{{ health.llm_model || '-' }}</p>
                    </div>
                </div>
                <div class="flex items-center gap-3 p-3 rounded-lg bg-gray-50/60">
                    <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-emerald-50">
                        <Globe :size="16" class="text-emerald-500" />
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs text-gray-400">LLM 状态</p>
                        <p class="text-sm font-medium truncate mt-0.5" :class="llmStatusClass">{{ llmStatusText }}</p>
                    </div>
                </div>
                <div class="grid grid-cols-3 gap-2 pt-1">
                    <div
                        class="flex flex-col items-center gap-1.5 py-3 rounded-lg bg-gray-50/60 cursor-pointer hover:bg-gray-100/60 transition-colors"
                        @click="router.push('/admin/channels')"
                    >
                        <Shield :size="16" class="text-cyan-500" />
                        <span class="text-xs text-gray-600">通道管理</span>
                    </div>
                    <div
                        class="flex flex-col items-center gap-1.5 py-3 rounded-lg bg-gray-50/60 cursor-pointer hover:bg-gray-100/60 transition-colors"
                        @click="router.push('/plugins')"
                    >
                        <Wrench :size="16" class="text-amber-500" />
                        <span class="text-xs text-gray-600">插件管理</span>
                    </div>
                    <div
                        class="flex flex-col items-center gap-1.5 py-3 rounded-lg bg-gray-50/60 cursor-pointer hover:bg-gray-100/60 transition-colors"
                        @click="router.push('/admin/agents')"
                    >
                        <Cpu :size="16" class="text-violet-500" />
                        <span class="text-xs text-gray-600">Agent 路由</span>
                    </div>
                </div>
            </div>
        </VortSpin>
    </vort-card>
</template>

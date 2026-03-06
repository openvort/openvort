<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { getHealthStatus } from "@/api";
import { Heart, Cpu, Globe, Wrench, Shield, ArrowRight } from "lucide-vue-next";

const router = useRouter();

const loading = ref(true);
const health = ref<{
    version?: string;
    llm_status?: string;
    model?: string;
    uptime?: string;
}>({});

onMounted(async () => {
    try {
        const res: any = await getHealthStatus();
        if (res) health.value = res;
    } catch { /* ignore */ }
    finally { loading.value = false; }
});

const infoItems = [
    { icon: Heart, label: "系统版本", key: "version", fallback: "-", color: "text-rose-500", bg: "bg-rose-50" },
    { icon: Cpu, label: "LLM 模型", key: "model", fallback: "-", color: "text-blue-500", bg: "bg-blue-50" },
    { icon: Globe, label: "LLM 状态", key: "llm_status", fallback: "-", color: "text-emerald-500", bg: "bg-emerald-50" },
];
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
                <div
                    v-for="item in infoItems" :key="item.key"
                    class="flex items-center gap-3 p-3 rounded-lg bg-gray-50/60"
                >
                    <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" :class="item.bg">
                        <component :is="item.icon" :size="16" :class="item.color" />
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs text-gray-400">{{ item.label }}</p>
                        <p class="text-sm font-medium text-gray-800 truncate mt-0.5">
                            <template v-if="item.key === 'llm_status'">
                                <span v-if="(health as any)[item.key] === 'ok'" class="text-green-600">正常</span>
                                <span v-else-if="(health as any)[item.key]" class="text-red-500">{{ (health as any)[item.key] }}</span>
                                <span v-else class="text-gray-400">{{ item.fallback }}</span>
                            </template>
                            <template v-else>
                                {{ (health as any)[item.key] || item.fallback }}
                            </template>
                        </p>
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

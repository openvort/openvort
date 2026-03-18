<template>
    <Drawer :open="open" width="520px" @update:open="$emit('update:open', $event)">
        <template #title>
            <div class="flex items-center gap-2">
                <StatusIcon v-if="job" :color="job.color" />
                <span>{{ job?.display_name || job?.name || "Job 详情" }}</span>
            </div>
        </template>

        <div v-if="loading" class="flex items-center justify-center py-12">
            <Loader2 class="w-5 h-5 animate-spin text-gray-400" />
        </div>

        <div v-else-if="job" class="space-y-6">
            <!-- Basic info -->
            <div class="space-y-3">
                <div v-if="job.description" class="text-sm text-gray-600">{{ job.description }}</div>
                <div class="grid grid-cols-2 gap-3 text-sm">
                    <div>
                        <span class="text-gray-400">状态</span>
                        <div class="mt-0.5 font-medium" :class="statusColor">{{ statusLabel }}</div>
                    </div>
                    <div>
                        <span class="text-gray-400">下次构建号</span>
                        <div class="mt-0.5 font-medium text-gray-800">#{{ job.next_build_number ?? "-" }}</div>
                    </div>
                    <div>
                        <span class="text-gray-400">队列中</span>
                        <div class="mt-0.5 font-medium" :class="job.in_queue ? 'text-amber-600' : 'text-gray-800'">{{ job.in_queue ? "是" : "否" }}</div>
                    </div>
                    <div>
                        <span class="text-gray-400">可构建</span>
                        <div class="mt-0.5 font-medium text-gray-800">{{ job.buildable ? "是" : "否" }}</div>
                    </div>
                </div>
            </div>

            <!-- Parameters -->
            <div v-if="job.parameters.length > 0">
                <h3 class="text-sm font-medium text-gray-700 mb-2">构建参数</h3>
                <div class="space-y-2">
                    <div v-for="p in job.parameters" :key="p.name" class="flex items-start gap-2 text-sm">
                        <span class="text-gray-500 shrink-0 font-mono bg-gray-100 px-1.5 py-0.5 rounded text-xs">{{ p.name }}</span>
                        <span class="text-gray-400">{{ p.type.replace("ParameterDefinition", "") }}</span>
                        <span v-if="p.default" class="text-gray-600">= {{ p.default }}</span>
                    </div>
                </div>
            </div>

            <!-- Build action -->
            <div>
                <VortButton class="w-full" @click="$emit('triggerBuild')">
                    <Play class="w-4 h-4 mr-1" /> 构建
                </VortButton>
            </div>

            <!-- Build history -->
            <div>
                <h3 class="text-sm font-medium text-gray-700 mb-2">构建历史</h3>
                <div v-if="job.builds.length === 0" class="text-sm text-gray-400 py-4 text-center">暂无构建记录</div>
                <div v-else class="space-y-1">
                    <div
                        v-for="build in job.builds"
                        :key="build.number"
                        class="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 text-sm"
                    >
                        <div class="flex items-center gap-2">
                            <StatusIcon :color="buildColor(build)" />
                            <span class="font-medium text-gray-800">#{{ build.number }}</span>
                            <span class="text-gray-400 text-xs">{{ formatRelativeTime(build.timestamp) }}</span>
                        </div>
                        <div class="flex items-center gap-3">
                            <span class="text-xs text-gray-400">{{ formatDuration(build.duration) }}</span>
                            <VortButton variant="text" size="small" @click="$emit('viewLog', build.number)">日志</VortButton>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </Drawer>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Loader2, Play } from "lucide-vue-next";
import { Drawer } from "@/components/vort";
import StatusIcon from "./StatusIcon.vue";
import { getColorStatus, formatDuration, formatRelativeTime } from "../types";
import type { JenkinsJobDetail, JenkinsBuild } from "../types";

const props = defineProps<{
    open: boolean;
    job: JenkinsJobDetail | null;
    loading: boolean;
}>();

defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "triggerBuild"): void;
    (e: "viewLog", buildNumber: number): void;
}>();

const statusInfo = computed(() => props.job ? getColorStatus(props.job.color) : null);
const statusLabel = computed(() => statusInfo.value?.label ?? "-");
const statusColor = computed(() => {
    switch (statusInfo.value?.variant) {
        case "success": return "text-green-600";
        case "error": return "text-red-600";
        case "warning": return "text-amber-600";
        default: return "text-gray-600";
    }
});

function buildColor(build: JenkinsBuild): string {
    if (build.building) return "blue_anime";
    switch (build.result) {
        case "SUCCESS": return "blue";
        case "FAILURE": return "red";
        case "UNSTABLE": return "yellow";
        case "ABORTED": return "aborted";
        default: return "grey";
    }
}
</script>

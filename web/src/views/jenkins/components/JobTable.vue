<template>
    <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Breadcrumbs -->
        <div v-if="breadcrumbs.length > 1" class="px-5 py-2 flex items-center gap-1 text-sm text-gray-500 border-b border-gray-100">
            <template v-for="(crumb, idx) in breadcrumbs" :key="idx">
                <span v-if="idx > 0" class="text-gray-300">/</span>
                <button
                    class="hover:text-blue-600 transition-colors"
                    :class="idx === breadcrumbs.length - 1 ? 'text-gray-800 font-medium' : ''"
                    @click="$emit('navigateBreadcrumb', crumb.path)"
                >
                    {{ crumb.label }}
                </button>
            </template>
        </div>

        <!-- Filter Bar -->
        <div class="px-5 py-3 flex items-center gap-3">
            <VortInputSearch
                :model-value="keyword"
                placeholder="搜索 Job..."
                allow-clear
                class="w-[240px]"
                @update:model-value="$emit('update:keyword', $event)"
                @search="$emit('search')"
                @keyup.enter="$emit('search')"
            />
            <AiAssistButton label="AI 管理 Job" :prompts="aiPrompts" />
        </div>

        <!-- Table -->
        <div class="flex-1 overflow-auto px-5 pb-4">
            <VortTable
                :data-source="jobs"
                :loading="loading"
                row-key="name"
                :pagination="false"
            >
                <VortTableColumn label="S" prop="color" :width="50">
                    <template #default="{ row }">
                        <StatusIcon :color="row.color" />
                    </template>
                </VortTableColumn>

                <VortTableColumn label="Name" prop="name" :min-width="220">
                    <template #default="{ row }">
                        <button
                            class="flex items-center gap-2 hover:text-blue-600 transition-colors text-left"
                            @click="row.is_folder ? $emit('enterFolder', row.name) : $emit('viewDetail', row)"
                        >
                            <FolderClosed v-if="row.is_folder" class="w-4 h-4 text-amber-500 shrink-0" />
                            <span :class="row.is_folder ? 'font-medium' : ''">{{ row.name }}</span>
                        </button>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="上次成功" :width="140">
                    <template #default="{ row }">
                        <template v-if="!row.is_folder && row.last_build?.result === 'SUCCESS'">
                            <span class="text-green-600">#{{ row.last_build.number }}</span>
                            <span class="ml-1 text-gray-400">{{ formatRelativeTime(row.last_build.timestamp) }}</span>
                        </template>
                        <span v-else-if="!row.is_folder" class="text-gray-300">-</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="上次失败" :width="140">
                    <template #default="{ row }">
                        <template v-if="!row.is_folder && row.last_build?.result === 'FAILURE'">
                            <span class="text-red-600">#{{ row.last_build.number }}</span>
                            <span class="ml-1 text-gray-400">{{ formatRelativeTime(row.last_build.timestamp) }}</span>
                        </template>
                        <span v-else-if="!row.is_folder" class="text-gray-300">-</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="上次耗时" :width="120">
                    <template #default="{ row }">
                        <template v-if="!row.is_folder && row.last_build?.duration">
                            <span class="text-gray-500">{{ formatDuration(row.last_build.duration) }}</span>
                        </template>
                        <span v-else-if="!row.is_folder" class="text-gray-300">-</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="操作" :width="100" align="center" fixed="right">
                    <template #default="{ row }">
                        <VortButton
                            v-if="!row.is_folder"
                            variant="text"
                            size="small"
                            :loading="buildingJob === row.name"
                            @click="$emit('triggerBuild', row)"
                        >
                            <Play v-if="buildingJob !== row.name" :size="14" class="mr-1" /> 构建
                        </VortButton>
                        <button
                            v-else
                            class="text-gray-400 hover:text-gray-600"
                            @click="$emit('enterFolder', row.name)"
                        >
                            <ChevronRight class="w-4 h-4" />
                        </button>
                    </template>
                </VortTableColumn>

                <template #empty>
                    <div class="flex flex-col items-center py-12 text-gray-400">
                        <HardDrive :size="48" class="mb-3 text-gray-300" />
                        <p class="text-sm">暂无 Job</p>
                    </div>
                </template>
            </VortTable>
        </div>
    </div>
</template>

<script setup lang="ts">
import { Play, ChevronRight, FolderClosed, HardDrive } from "lucide-vue-next";
import { AiAssistButton } from "@/components/vort-biz/ai-assist-button";
import type { AiAssistPromptItem } from "@/components/vort-biz/ai-assist-button";
import StatusIcon from "./StatusIcon.vue";
import { formatDuration, formatRelativeTime } from "../types";
import type { JenkinsJob } from "../types";

const aiPrompts: AiAssistPromptItem[] = [
    {
        label: "新增 Job",
        prompt: "我想在 Jenkins 上创建一个新的 Job，请先用 jenkins_manage_instance(action=list) 查看可用实例，然后引导我完成创建。请询问我 Job 类型（Freestyle/Pipeline）、构建步骤、参数化需求等信息。",
    },
    {
        label: "编辑 Job 配置",
        prompt: "我想修改一个 Jenkins Job 的配置，请先用 jenkins_manage_instance(action=list) 查看可用实例，然后用 jenkins_list_jobs 帮我找到目标 Job，获取它的当前配置并引导我完成修改。",
    },
    {
        label: "复制 Job",
        prompt: "我想复制一个 Jenkins Job，请先用 jenkins_manage_instance(action=list) 查看可用实例，然后用 jenkins_list_jobs 帮我找到要复制的源 Job，询问新名称和目标文件夹。",
    },
    {
        label: "删除 Job",
        prompt: "我想删除一个 Jenkins Job，请先用 jenkins_manage_instance(action=list) 查看可用实例，然后用 jenkins_list_jobs 帮我找到要删除的 Job，确认后执行删除。",
    },
];

defineProps<{
    jobs: JenkinsJob[];
    breadcrumbs: { label: string; path: string[] }[];
    keyword: string;
    loading: boolean;
    buildingJob: string;
}>();

defineEmits<{
    (e: "enterFolder", folderName: string): void;
    (e: "viewDetail", job: JenkinsJob): void;
    (e: "triggerBuild", job: JenkinsJob): void;
    (e: "navigateBreadcrumb", path: string[]): void;
    (e: "update:keyword", val: string): void;
    (e: "search"): void;
}>();
</script>

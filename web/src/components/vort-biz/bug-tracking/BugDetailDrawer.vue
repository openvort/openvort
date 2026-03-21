<script setup lang="ts">
import { computed } from "vue";
import { Pencil } from "lucide-vue-next";
import type { RowItem, Priority, Status, WorkType, DateRange, DetailComment, DetailLog } from "./types";
import {
    priorityOptions,
    statusFilterOptions,
    priorityLabelMap,
    statusIconMap,
    priorityClassMap,
    statusClassMap,
    createBugTagOptions
} from "./types";

interface Props {
    state: ReturnType<typeof import("./useBugTrackingState").useBugTrackingState>;
}

const props = defineProps<Props>();

const avatarBgPalette = ["#2f80ed", "#5b8ff9", "#9b59b6", "#27ae60", "#f39c12", "#e67e22", "#16a085", "#8e44ad"];
const getAvatarBg = (name: string): string => {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return avatarBgPalette[Math.abs(hash) % avatarBgPalette.length]!;
};

const tagColorPalette = ["#ef4444", "#d946ef", "#eab308", "#22c55e", "#3b82f6", "#f97316", "#14b8a6", "#8b5cf6"];
const getTagColor = (name: string): string => {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return tagColorPalette[Math.abs(hash) % tagColorPalette.length]!;
};

const hasDetailRecord = computed(() => !!props.state.detailCurrentRecord.value);

const closeDrawer = () => {
    props.state.detailSelectedWorkNo.value = "";
};
</script>

<template>
    <vort-drawer
        v-model:open="props.state.detailSelectedWorkNo.value"
        :title="`缺陷详情 - ${props.state.detailCurrentRecord.value?.workNo || ''}`"
        :width="720"
        @close="closeDrawer"
    >
        <div v-if="hasDetailRecord" class="h-full flex flex-col">
            <!-- 头部信息 -->
            <div class="pb-4 border-b border-gray-100">
                <div class="flex items-start gap-3 mb-3">
                    <span
                        class="w-8 h-8 rounded flex items-center justify-center text-white text-sm flex-shrink-0"
                        :class="props.state.detailCurrentRecord.value?.type === '缺陷' ? 'bg-red-500' : props.state.detailCurrentRecord.value?.type === '需求' ? 'bg-blue-500' : 'bg-green-500'"
                    >
                        {{ props.state.detailCurrentRecord.value?.type === '缺陷' ? '✹' : props.state.detailCurrentRecord.value?.type === '需求' ? '≡' : '☑' }}
                    </span>
                    <div class="flex-1 min-w-0">
                        <h3 class="text-lg font-medium text-gray-900 break-words">{{ props.state.detailCurrentRecord.value?.title }}</h3>
                        <div class="flex items-center gap-3 mt-2 flex-wrap">
                            <span
                                class="px-2 py-0.5 text-xs rounded border"
                                :class="priorityClassMap[props.state.detailCurrentRecord.value?.priority as Priority]"
                            >
                                {{ priorityLabelMap[props.state.detailCurrentRecord.value?.priority as Priority] }}
                            </span>
                            <span
                                class="px-2 py-0.5 text-xs rounded border"
                                :class="statusClassMap[props.state.detailCurrentRecord.value?.status as Status]"
                            >
                                <span class="mr-1">{{ statusIconMap[props.state.detailCurrentRecord.value?.status as Status] }}</span>
                                {{ props.state.detailCurrentRecord.value?.status }}
                            </span>
                            <span class="text-sm text-gray-500">创建人：{{ props.state.detailCurrentRecord.value?.creator }}</span>
                            <span class="text-sm text-gray-500">创建时间：{{ props.state.detailCurrentRecord.value?.createdAt }}</span>
                        </div>
                    </div>
                </div>

                <!-- 标签 -->
                <div v-if="props.state.detailCurrentRecord.value?.tags?.length" class="flex items-center gap-2 flex-wrap mt-2">
                    <span
                        v-for="tag in props.state.detailCurrentRecord.value.tags"
                        :key="tag"
                        class="px-2 py-0.5 rounded text-xs text-white"
                        :style="{ backgroundColor: getTagColor(tag) }"
                    >
                        {{ tag }}
                    </span>
                </div>
            </div>

            <!-- Tab 切换 -->
            <div class="flex-1 overflow-hidden flex flex-col mt-4">
                <vort-tabs v-model:activeKey="props.state.detailActiveTab.value" class="flex-1 flex flex-col overflow-hidden">
                    <vort-tab-pane tab-key="detail" tab="详情" class="overflow-y-auto">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <!-- 负责人 -->
                            <div>
                                <span class="text-sm text-gray-400">负责人</span>
                                <div class="flex items-center gap-2 mt-1">
                                    <span
                                        v-if="props.state.detailCurrentRecord.value?.owner"
                                        class="w-6 h-6 rounded-full text-white text-xs flex items-center justify-center"
                                        :style="{ backgroundColor: getAvatarBg(props.state.detailCurrentRecord.value?.owner || '') }"
                                    >
                                        {{ props.state.detailCurrentRecord.value?.owner.slice(0, 1).toUpperCase() }}
                                    </span>
                                    <span class="text-sm text-gray-800">{{ props.state.detailCurrentRecord.value?.owner || '未指派' }}</span>
                                </div>
                            </div>

                            <!-- 协作人 -->
                            <div>
                                <span class="text-sm text-gray-400">协作人</span>
                                <div class="flex items-center gap-1 mt-1 flex-wrap">
                                    <template v-if="props.state.detailCurrentRecord.value?.collaborators?.length">
                                        <span
                                            v-for="(member, idx) in props.state.detailCurrentRecord.value.collaborators"
                                            :key="idx"
                                            class="w-6 h-6 rounded-full text-white text-xs flex items-center justify-center"
                                            :style="{ backgroundColor: getAvatarBg(member) }"
                                        >
                                            {{ member.slice(0, 1).toUpperCase() }}
                                        </span>
                                    </template>
                                    <span v-else class="text-sm text-gray-400">暂无</span>
                                </div>
                            </div>

                            <!-- 计划时间 -->
                            <div>
                                <span class="text-sm text-gray-400">计划时间</span>
                                <div class="text-sm text-gray-800 mt-1">
                                    {{ props.state.detailCurrentRecord.value?.planTime?.[0] || '-' }} ~ {{ props.state.detailCurrentRecord.value?.planTime?.[1] || '-' }}
                                </div>
                            </div>

                            <!-- 类型 -->
                            <div>
                                <span class="text-sm text-gray-400">类型</span>
                                <div class="text-sm text-gray-800 mt-1">{{ props.state.detailCurrentRecord.value?.type }}</div>
                            </div>
                        </div>

                        <!-- 描述 -->
                        <div class="mt-4">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-sm text-gray-400">描述</span>
                                <button v-if="!props.state.detailDescEditing.value" class="text-blue-600 text-sm flex items-center gap-1 hover:text-blue-700" @click="props.state.openDetailDescEditor()">
                                    <Pencil :size="14" /> 编辑
                                </button>
                            </div>
                            <div v-if="props.state.detailDescEditing.value" class="space-y-2">
                                <vort-textarea
                                    v-model="props.state.detailDescDraft.value"
                                    :rows="6"
                                    placeholder="请输入描述"
                                />
                                <div class="flex justify-end gap-2">
                                    <vort-button size="small" @click="props.state.cancelDetailDescEditor()">取消</vort-button>
                                    <vort-button variant="primary" size="small" @click="props.state.saveDetailDescEditor()">保存</vort-button>
                                </div>
                            </div>
                            <div v-else class="text-sm text-gray-800 whitespace-pre-wrap min-h-[80px] p-2 border border-transparent hover:border-gray-100 rounded">
                                {{ props.state.detailCurrentRecord.value?.description || '暂无描述' }}
                            </div>
                        </div>
                    </vort-tab-pane>

                    <vort-tab-pane tab-key="comments" tab="评论" class="overflow-y-auto">
                        <div class="flex flex-col h-full">
                            <!-- 评论列表 -->
                            <div class="flex-1 overflow-y-auto space-y-4 mb-4">
                                <div
                                    v-for="comment in props.state.detailComments.value"
                                    :key="comment.id"
                                    class="flex gap-3"
                                >
                                    <span
                                        class="w-8 h-8 rounded-full text-white text-sm flex items-center justify-center flex-shrink-0"
                                        :style="{ backgroundColor: getAvatarBg(comment.author) }"
                                    >
                                        {{ comment.author.slice(0, 1).toUpperCase() }}
                                    </span>
                                    <div class="flex-1">
                                        <div class="flex items-center gap-2">
                                            <span class="text-sm font-medium text-gray-800">{{ comment.author }}</span>
                                            <span class="text-xs text-gray-400">{{ comment.createdAt }}</span>
                                        </div>
                                        <div class="text-sm text-gray-600 mt-1">{{ comment.content }}</div>
                                    </div>
                                </div>
                                <div v-if="!props.state.detailComments.value.length" class="text-center text-gray-400 py-8">
                                    暂无评论
                                </div>
                            </div>

                            <!-- 评论输入 -->
                            <div class="border-t border-gray-100 pt-4">
                                <vort-textarea
                                    v-model="props.state.detailCommentDraft.value"
                                    :rows="3"
                                    placeholder="添加评论..."
                                />
                                <div class="flex justify-end mt-2">
                                    <vort-button variant="primary" size="small" :disabled="!props.state.detailCommentDraft.value.trim()" @click="props.state.submitDetailComment()">
                                        提交评论
                                    </vort-button>
                                </div>
                            </div>
                        </div>
                    </vort-tab-pane>

                    <vort-tab-pane tab-key="logs" tab="日志" class="overflow-y-auto">
                        <div class="space-y-3">
                            <div
                                v-for="log in props.state.detailLogs.value"
                                :key="log.id"
                                class="flex gap-3 text-sm"
                            >
                                <span
                                    class="w-8 h-8 rounded-full text-white text-sm flex items-center justify-center flex-shrink-0"
                                    :style="{ backgroundColor: getAvatarBg(log.actor) }"
                                >
                                    {{ log.actor.slice(0, 1).toUpperCase() }}
                                </span>
                                <div class="flex-1">
                                    <div class="flex items-center gap-2">
                                        <span class="text-gray-800">{{ log.actor }}</span>
                                        <span class="text-gray-500">{{ log.action }}</span>
                                    </div>
                                    <span class="text-xs text-gray-400">{{ log.createdAt }}</span>
                                </div>
                            </div>
                            <div v-if="!props.state.detailLogs.value.length" class="text-center text-gray-400 py-8">
                                暂无日志
                            </div>
                        </div>
                    </vort-tab-pane>
                </vort-tabs>
            </div>
        </div>
    </vort-drawer>
</template>

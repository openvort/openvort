<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ProTable, type ProTableColumn } from "@/components/vort-biz/pro-table";
import { Pencil } from "lucide-vue-next";
import StatusIcon from "@/components/vort-biz/work-item/StatusIcon.vue";
import type { RowItem, Priority, Status, WorkType, DateRange } from "./types";
import {
    priorityOptions,
    statusFilterOptions,
    priorityLabelMap,
    statusIconMap,
    priorityClassMap,
    statusClassMap,
    tagOptions
} from "./types";

interface Props {
    state: ReturnType<typeof import("./useBugTrackingState").useBugTrackingState>;
}

const props = defineProps<Props>();
const tableRef = ref<any>(null);

onMounted(() => {
    if (props.state.tableRef) {
        props.state.tableRef.value = tableRef.value;
    }
});

// 辅助函数
const getWorkTypeIconClass = (type: WorkType): string => {
    if (type === "需求") return "work-type-icon-demand";
    if (type === "任务") return "work-type-icon-task";
    return "work-type-icon-bug";
};

const getWorkTypeIconSymbol = (type: WorkType): string => {
    if (type === "需求") return "≡";
    if (type === "任务") return "☑";
    return "✹";
};

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

const getCollapsedTags = (tags: string[], resolvedWidth?: string | number): { visible: string[]; hidden: number } => {
    const maxWidth = typeof resolvedWidth === "number" ? resolvedWidth : parseInt(resolvedWidth || "150") || 150;
    let currentWidth = 0;
    const visible: string[] = [];
    let hidden = 0;

    for (const tag of tags) {
        const tagWidth = tag.length * 12 + 12;
        if (currentWidth + tagWidth < maxWidth && visible.length < 3) {
            visible.push(tag);
            currentWidth += tagWidth;
        } else {
            hidden++;
        }
    }

    return { visible, hidden };
};

const getTagRenderInfo = (record: RowItem, text: string[] | undefined, resolvedWidth?: string | number) => {
    return getCollapsedTags(props.state.getRowTags(record, text), resolvedWidth);
};

const columns = computed<ProTableColumn<RowItem>[]>(() => [
    {
        title: "工作项",
        dataIndex: "title",
        width: 420,
        fixed: "left"
    },
    {
        title: "状态",
        dataIndex: "status",
        width: 120
    },
    {
        title: "优先级",
        dataIndex: "priority",
        width: 100
    },
    {
        title: "标签",
        dataIndex: "tags",
        width: 150
    },
    {
        title: "负责人",
        dataIndex: "owner",
        width: 150
    },
    {
        title: "协作人",
        dataIndex: "collaborators",
        width: 180
    },
    {
        title: "计划时间",
        dataIndex: "planTime",
        width: 160
    },
    {
        title: "创建时间",
        dataIndex: "createdAt",
        width: 160
    }
]);

const onReset = () => {
    props.state.onReset();
    props.state.tableRef?.refresh?.();
};
</script>

<template>
    <div class="p-6 space-y-4" @click="props.state.onGlobalClick">
        <!-- 搜索卡片 -->
        <div class="bg-white rounded-xl p-4">
            <h3 class="text-base font-medium text-gray-800 mb-3">缺陷</h3>
            <div class="flex flex-wrap items-center gap-3 text-sm">
                <div class="text-gray-600"><span class="text-gray-900 font-medium">共{{ props.state.totalCount || props.state.allData.length }}项</span></div>
                <input v-model="props.state.keyword.value" placeholder="输入关键词" class="h-8 px-3 border border-gray-300 rounded w-[180px]" />
                
                <!-- 负责人下拉 -->
                <div class="relative" @click.stop>
                    <button
                        class="h-8 min-w-[130px] px-3 border border-slate-300 rounded-md bg-white flex items-center justify-between text-left hover:border-slate-400"
                        :class="{ 'border-blue-500 ring-1 ring-blue-200': props.state.ownerDropdownOpen.value }"
                        @click.stop="props.state.ownerDropdownOpen.value = !props.state.ownerDropdownOpen.value"
                    >
                        <span class="text-sm text-gray-700">{{ props.state.owner.value || "负责人" }}</span>
                        <span class="status-arrow-simple" :class="{ open: props.state.ownerDropdownOpen.value }" />
                    </button>
                    <div v-if="props.state.ownerDropdownOpen.value" class="absolute z-30 mt-1 w-[260px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                        <div class="mb-2">
                            <div class="relative">
                                <input v-model="props.state.ownerKeyword.value" placeholder="搜索..." class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm" />
                                <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                            </div>
                        </div>
                        <div class="max-h-[460px] overflow-y-auto -mx-3">
                            <button class="w-full h-10 px-3 text-left text-gray-700 hover:bg-gray-50" @click.stop="props.state.selectOwner('')">全部</button>
                            <button class="w-full h-10 px-3 text-left text-gray-700 hover:bg-gray-50" @click.stop="props.state.selectOwner('未指派')">未指派</button>
                            <div v-for="group in props.state.filteredOwnerGroups.value" :key="group.label">
                                <button class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left" @click.stop="props.state.toggleOwnerGroup(group.label)">
                                    <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                    <span class="status-arrow-simple" :class="{ open: props.state.isGroupOpen(props.state.ownerGroupOpen, group.label) }" />
                                </button>
                                <button
                                    v-for="member in (props.state.isGroupOpen(props.state.ownerGroupOpen, group.label) ? group.members : [])"
                                    :key="group.label + member"
                                    class="w-full h-10 px-3 flex items-center gap-2 text-left hover:bg-gray-50"
                                    @click.stop="props.state.selectOwner(member)"
                                >
                                    <span class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center" :style="{ backgroundColor: getAvatarBg(member) }">
                                        {{ member.slice(0, 1).toUpperCase() }}
                                    </span>
                                    <span class="text-sm text-gray-700">{{ member }}</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 类型下拉 -->
                <div class="relative" @click.stop>
                    <button
                        class="h-8 min-w-[110px] px-3 border border-slate-300 rounded-md bg-white flex items-center justify-between text-left hover:border-slate-400"
                        :class="{ 'border-blue-500 ring-1 ring-blue-200': props.state.typeDropdownOpen.value }"
                        @click.stop="props.state.typeDropdownOpen.value = !props.state.typeDropdownOpen.value"
                    >
                        <span class="text-sm text-gray-700">{{ props.state.type.value || "类型" }}</span>
                        <span class="status-arrow-simple" :class="{ open: props.state.typeDropdownOpen.value }" />
                    </button>
                    <div v-if="props.state.typeDropdownOpen.value" class="absolute z-30 mt-1 w-[180px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                        <div class="mb-2">
                            <div class="relative">
                                <input v-model="props.state.typeKeyword.value" placeholder="搜索..." class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm" />
                                <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                            </div>
                        </div>
                        <div class="max-h-[260px] overflow-y-auto -mx-3">
                            <div v-for="group in props.state.typeGroups.value" :key="group">
                                <button class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left" @click.stop="props.state.toggleTypeGroup(group)">
                                    <span class="text-gray-700 text-sm">{{ group }}</span>
                                    <span class="status-arrow-simple" :class="{ open: props.state.typeGroupOpen[group] }" />
                                </button>
                                <button
                                    v-if="props.state.typeGroupOpen[group]"
                                    class="w-full h-10 px-3 flex items-center gap-3 text-left hover:bg-gray-50"
                                    @click.stop="props.state.selectType(group)"
                                >
                                    <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                        <span v-if="props.state.type.value === group">✓</span>
                                    </span>
                                    <span class="text-gray-700 text-sm">{{ group }}</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 状态下拉 -->
                <div class="relative" @click.stop>
                    <button
                        class="h-8 min-w-[130px] px-3 border border-slate-300 rounded-md bg-white flex items-center justify-between text-left hover:border-slate-400"
                        @click.stop="props.state.statusDropdownOpen.value = !props.state.statusDropdownOpen.value"
                    >
                        <span class="text-sm text-gray-700">{{ props.state.status.value || "状态" }}</span>
                        <span class="status-arrow-simple" />
                    </button>
                    <div v-if="props.state.statusDropdownOpen.value" class="absolute z-30 mt-1 w-[240px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                        <div class="mb-2">
                            <input v-model="props.state.statusKeyword.value" placeholder="搜索..." class="w-full h-9 px-3 border border-gray-300 rounded-md text-sm" />
                        </div>
                        <div class="max-h-[220px] overflow-y-auto pr-1">
                            <button
                                v-for="opt in props.state.filteredStatusOptions.value"
                                :key="opt.value"
                                class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                :class="{ 'bg-slate-100': props.state.status.value === opt.value }"
                                @click.stop="props.state.selectStatus(opt.value)"
                            >
                                <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                    <span v-if="props.state.status.value === opt.value">✓</span>
                                </span>
                                <span class="leading-none w-4 text-center flex items-center justify-center" :class="opt.iconClass"><StatusIcon :name="opt.icon" :size="14" /></span>
                                <span class="text-sm text-gray-700">{{ opt.label }}</span>
                            </button>
                        </div>
                    </div>
                </div>

                <button class="h-8 px-4 bg-blue-600 text-white rounded hover:bg-blue-700" @click="props.state.tableRef?.refresh?.()">查询</button>
                <button class="h-8 px-4 border border-gray-300 rounded hover:bg-gray-50" @click="onReset">重置</button>
                <button class="h-8 px-4 bg-blue-600 text-white rounded hover:bg-blue-700 ml-auto" @click="props.state.handleCreateBug()">+ 新建缺陷</button>
            </div>
        </div>

        <!-- 表格卡片 -->
        <div class="bg-white rounded-xl p-4">
            <ProTable
                ref="tableRef"
                :columns="columns"
                :request="props.state.request"
                :params="props.state.queryParams"
                :pagination="{ pageSize: 20, showSizeChanger: true, showQuickJumper: true, pageSizeOptions: [10, 20, 50] }"
                :toolbar="false"
                bordered
            >
                <!-- 标题列 -->
                <template #title="{ text, record }">
                    <button class="title-link-cell" :title="text" @click.stop="props.state.handleOpenBugDetail(record)">
                        <span class="work-type-icon" :class="getWorkTypeIconClass(record.type)">
                            <svg v-if="record.type === '缺陷'" class="work-type-icon-svg" viewBox="0 0 24 24" aria-hidden="true">
                                <circle cx="12" cy="7.5" r="3.2" fill="white" />
                                <rect x="8" y="10.5" width="8" height="9" rx="3.8" fill="white" />
                                <rect x="11.2" y="10.8" width="1.6" height="8.6" rx="0.8" fill="#ef4444" />
                                <path d="M8.3 12.3H5.2M8.1 15.1H4.8M15.9 12.3H18.8M16.1 15.1H19.2" stroke="white" stroke-width="1.5" stroke-linecap="round" />
                                <path d="M10.2 4.8 8.7 3.3M13.8 4.8 15.3 3.3" stroke="white" stroke-width="1.5" stroke-linecap="round" />
                            </svg>
                            <template v-else>
                                {{ getWorkTypeIconSymbol(record.type) }}
                            </template>
                        </span>
                        <span class="title-link-text">{{ text }}</span>
                    </button>
                </template>

                <!-- 优先级列 -->
                <template #priority="{ text, record }">
                    <div class="relative inline-block text-left" @click.stop>
                        <button
                            class="h-7 px-2 text-xs rounded border leading-none"
                            :class="priorityClassMap[props.state.getRowPriority(record, text as Priority)]"
                            @click.stop="props.state.togglePriorityMenu(record.workNo)"
                        >
                            {{ priorityLabelMap[props.state.getRowPriority(record, text as Priority)] }}
                        </button>
                        <div v-if="props.state.openPriorityFor.value === record.workNo" class="absolute z-20 mt-1 w-[112px] bg-white border border-gray-200 rounded-md shadow-sm py-1">
                            <button
                                v-for="opt in priorityOptions"
                                :key="opt.value"
                                class="w-full text-left px-2 py-1 text-xs hover:bg-gray-50"
                                @click.stop="props.state.selectPriority(record.workNo, opt.value)"
                            >
                                <span class="inline-block px-1.5 py-0.5 rounded border" :class="priorityClassMap[opt.value]">
                                    {{ opt.label }}
                                </span>
                            </button>
                        </div>
                    </div>
                </template>

                <!-- 标签列 -->
                <template #tags="{ text, record, resolvedWidth }">
                    <div class="relative inline-block w-full" @click.stop>
                        <button class="w-full text-left" @click.stop="props.state.toggleTagMenu(record.workNo)">
                            <div class="flex items-center gap-1 flex-nowrap whitespace-nowrap overflow-hidden">
                                <template v-for="tag in getTagRenderInfo(record, text as string[], resolvedWidth).visible" :key="record.workNo + '-' + tag">
                                    <span class="px-1.5 py-0.5 rounded text-xs text-white inline-block" :style="{ backgroundColor: getTagColor(tag) }">
                                        {{ tag }}
                                    </span>
                                </template>
                                <span v-if="getTagRenderInfo(record, text as string[], resolvedWidth).hidden > 0" class="text-gray-400 font-medium text-sm">
                                    +{{ getTagRenderInfo(record, text as string[], resolvedWidth).hidden }}
                                </span>
                            </div>
                        </button>
                        <div v-if="props.state.openTagFor.value === record.workNo" class="absolute z-30 mt-1 w-[240px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                            <div class="mb-2">
                                <div class="relative">
                                    <input v-model="props.state.tagKeyword.value" placeholder="搜索..." class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm" />
                                    <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                </div>
                            </div>
                            <div class="max-h-[200px] overflow-y-auto pr-1">
                                <button
                                    v-for="tag in props.state.filteredTagOptions.value"
                                    :key="record.workNo + '-opt-' + tag"
                                    class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                    @click.stop="props.state.toggleTagOption(record, tag, text as string[])"
                                >
                                    <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                        <span v-if="props.state.getRowTags(record, text as string[]).includes(tag)">✓</span>
                                    </span>
                                    <span class="w-5 h-5 rounded-full" :style="{ backgroundColor: getTagColor(tag) }" />
                                    <span class="text-sm text-gray-700">{{ tag }}</span>
                                </button>
                            </div>
                            <div class="mt-2 flex justify-end">
                                <button class="h-8 px-3 text-sm bg-blue-600 text-white rounded hover:bg-blue-700" @click.stop="props.state.finishTagEdit()">完成</button>
                            </div>
                        </div>
                    </div>
                </template>

                <!-- 状态列 -->
                <template #status="{ text, record }">
                    <div class="relative inline-block text-left" @click.stop>
                        <button class="status-edit-trigger" @click.stop="props.state.toggleRowStatusMenu(record.workNo)">
                            <span class="status-badge table-status-badge" :class="statusClassMap[props.state.getRowStatus(record, text as Status)]">
                                <span class="status-badge-icon"><StatusIcon :name="statusIconMap[props.state.getRowStatus(record, text as Status)]" :size="12" /></span>
                                <span>{{ props.state.getRowStatus(record, text as Status) }}</span>
                            </span>
                        </button>
                        <div v-if="props.state.openStatusFor.value === record.workNo" class="absolute z-30 mt-1 w-[240px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                            <div class="mb-2">
                                <input v-model="props.state.rowStatusKeyword.value" placeholder="搜索..." class="w-full h-9 px-3 border border-gray-300 rounded-md text-sm" />
                            </div>
                            <div class="max-h-[220px] overflow-y-auto pr-1">
                                <button
                                    v-for="opt in props.state.filteredRowStatusOptions.value"
                                    :key="record.workNo + '-status-' + opt.value"
                                    class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                    :class="{ 'bg-slate-100': props.state.getRowStatus(record, text as Status) === opt.value }"
                                    @click.stop="props.state.selectRowStatus(record, opt.value)"
                                >
                                    <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                        <span v-if="props.state.getRowStatus(record, text as Status) === opt.value">✓</span>
                                    </span>
                                    <span class="leading-none w-4 text-center flex items-center justify-center" :class="opt.iconClass"><StatusIcon :name="opt.icon" :size="14" /></span>
                                    <span class="text-sm text-gray-700">{{ opt.label }}</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </template>

                <!-- 负责人列 -->
                <template #owner="{ text, record }">
                    <div class="relative inline-block" @click.stop>
                        <button
                            class="h-8 max-w-[150px] px-2 rounded-md bg-transparent flex items-center gap-2"
                            :class="{ 'ring-1 ring-blue-200': props.state.openOwnerFor.value === record.workNo }"
                            @click.stop="props.state.toggleRowOwnerMenu(record.workNo)"
                        >
                            <span
                                v-if="props.state.getRowOwner(record, text)"
                                class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center flex-shrink-0"
                                :style="{ backgroundColor: getAvatarBg(props.state.getRowOwner(record, text)) }"
                            >
                                {{ props.state.getRowOwner(record, text).slice(0, 1).toUpperCase() }}
                            </span>
                            <span class="text-sm text-gray-700 truncate">{{ props.state.getRowOwner(record, text) || "未指派" }}</span>
                        </button>
                        <div v-if="props.state.openOwnerFor.value === record.workNo" class="absolute z-30 mt-1 w-[260px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                            <div class="mb-2">
                                <div class="relative">
                                    <input v-model="props.state.ownerEditKeyword.value" placeholder="搜索..." class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm" />
                                    <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                </div>
                            </div>
                            <div class="max-h-[300px] overflow-y-auto -mx-3">
                                <button class="w-full h-10 px-3 text-left text-gray-700 hover:bg-gray-50" @click.stop="props.state.selectRowOwner(record, '')">取消指派</button>
                                <div v-for="group in props.state.filteredOwnerEditGroups.value" :key="group.label + '-edit'">
                                    <button class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left" @click.stop="props.state.toggleOwnerEditGroup(group.label)">
                                        <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                        <span class="status-arrow-simple" :class="{ open: props.state.isGroupOpen(props.state.ownerEditGroupOpen, group.label) }" />
                                    </button>
                                    <button
                                        v-for="member in (props.state.isGroupOpen(props.state.ownerEditGroupOpen, group.label) ? group.members : [])"
                                        :key="group.label + member + '-edit'"
                                        class="w-full h-10 px-3 flex items-center gap-2 text-left hover:bg-gray-50"
                                        @click.stop="props.state.selectRowOwner(record, member)"
                                    >
                                        <span class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center" :style="{ backgroundColor: getAvatarBg(member) }">
                                            {{ member.slice(0, 1).toUpperCase() }}
                                        </span>
                                        <span class="text-sm text-gray-700">{{ member }}</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </template>

                <!-- 协作人列 -->
                <template #collaborators="{ text, record }">
                    <div class="relative inline-block" @click.stop>
                        <button
                            class="h-8 px-2 rounded-md bg-transparent flex items-center gap-1 min-w-[60px]"
                            :class="{ 'ring-1 ring-blue-200': props.state.openCollaboratorFor.value === record.workNo }"
                            @click.stop="props.state.toggleCollaboratorMenu(record.workNo)"
                        >
                            <template v-if="props.state.getRowCollaborators(record, text as string[]).length > 0">
                                <span
                                    v-for="(member, idx) in props.state.getRowCollaborators(record, text as string[]).slice(0, 3)"
                                    :key="record.workNo + '-collab-' + idx"
                                    class="w-6 h-6 rounded-full text-white text-[10px] flex items-center justify-center flex-shrink-0 -ml-1 first:ml-0"
                                    :style="{ backgroundColor: getAvatarBg(member) }"
                                >
                                    {{ member.slice(0, 1).toUpperCase() }}
                                </span>
                                <span v-if="props.state.getRowCollaborators(record, text as string[]).length > 3" class="text-xs text-gray-400">
                                    +{{ props.state.getRowCollaborators(record, text as string[]).length - 3 }}
                                </span>
                            </template>
                            <span v-else class="text-sm text-gray-400">添加</span>
                        </button>
                        <div v-if="props.state.openCollaboratorFor.value === record.workNo" class="absolute z-30 mt-1 w-[260px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                            <div class="mb-2">
                                <div class="relative">
                                    <input v-model="props.state.collaboratorKeyword.value" placeholder="搜索..." class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm" />
                                    <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                </div>
                            </div>
                            <div class="max-h-[300px] overflow-y-auto -mx-3">
                                <div v-for="group in props.state.filteredCollaboratorGroups.value" :key="group.label + '-collab'">
                                    <button class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left" @click.stop="props.state.toggleCollaboratorGroup(group.label)">
                                        <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                        <span class="status-arrow-simple" :class="{ open: props.state.isGroupOpen(props.state.collaboratorGroupOpen, group.label) }" />
                                    </button>
                                    <button
                                        v-for="member in (props.state.isGroupOpen(props.state.collaboratorGroupOpen, group.label) ? group.members : [])"
                                        :key="group.label + member + '-collab'"
                                        class="w-full h-10 px-3 flex items-center gap-2 text-left hover:bg-gray-50"
                                        @click.stop="props.state.toggleRowCollaborator(record, member, text as string[])"
                                    >
                                        <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                            <span v-if="props.state.getRowCollaborators(record, text as string[]).includes(member)">✓</span>
                                        </span>
                                        <span class="w-6 h-6 rounded-full text-white text-[10px] flex items-center justify-center" :style="{ backgroundColor: getAvatarBg(member) }">
                                            {{ member.slice(0, 1).toUpperCase() }}
                                        </span>
                                        <span class="text-sm text-gray-700">{{ member }}</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </template>

                <!-- 计划时间列 -->
                <template #planTime="{ text, record }">
                    <div class="relative inline-block text-left" @click.stop>
                        <button
                            class="h-7 px-2 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:border-blue-300"
                            @click.stop="props.state.togglePlanTimeMenu(record.workNo)"
                        >
                            {{ props.state.getRowPlanTimeText(record, text as DateRange) }}
                        </button>
                        <div v-if="props.state.openPlanTimeFor.value === record.workNo" class="absolute z-30 mt-1 w-[280px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                            <vort-range-picker
                                :model-value="props.state.getRowPlanTime(record, text as DateRange)"
                                value-format="YYYY-MM-DD"
                                :placeholder="['开始日期', '结束日期']"
                                @update:model-value="props.state.onPlanTimeChange(record.workNo, $event as DateRange)"
                            />
                            <div class="mt-2 flex justify-end">
                                <button class="h-8 px-3 text-sm bg-blue-600 text-white rounded hover:bg-blue-700" @click.stop="props.state.togglePlanTimeMenu(record.workNo)">确定</button>
                            </div>
                        </div>
                    </div>
                </template>

                <!-- 创建时间列 -->
                <template #createdAt="{ text }">
                    <span class="text-sm text-gray-500">{{ text }}</span>
                </template>
            </ProTable>
        </div>
    </div>
</template>

<style scoped>
@reference "../../../assets/styles/index.css";

.title-link-cell {
    @apply flex items-center gap-2 cursor-pointer max-w-full;
}

.title-link-text {
    @apply truncate text-blue-600 hover:underline;
}

.work-type-icon {
    @apply w-5 h-5 flex items-center justify-center flex-shrink-0 rounded text-white text-xs;
}

.work-type-icon-bug {
    @apply bg-red-500;
}

.work-type-icon-demand {
    @apply bg-blue-500;
}

.work-type-icon-task {
    @apply bg-green-500;
}

.work-type-icon-svg {
    width: 16px;
    height: 16px;
}

.status-arrow-simple {
    @apply w-2 h-2 border-r-2 border-b-2 border-gray-400 -rotate-45 transition-transform;
}

.status-arrow-simple.open {
    @apply rotate-[135deg] -mt-0.5;
}

.status-edit-trigger {
    @apply cursor-pointer;
}

.status-badge {
    @apply inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border;
}

.status-badge-icon {
    @apply text-[10px];
}

.table-status-badge {
    @apply min-w-[70px] justify-center;
}
</style>

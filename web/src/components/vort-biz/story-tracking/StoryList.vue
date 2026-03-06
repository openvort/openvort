<script setup lang="ts">
import { ref, reactive, computed } from "vue";
import { useRouter } from "vue-router";
import { z } from "zod";
import { Popover } from "@openvort/vort-ui";
import { useCrudPage, useDirtyCheck } from "@/hooks";
import {
    getVortflowStories, getVortflowProjects, createVortflowStory,
    updateVortflowStory, deleteVortflowStory, transitionVortflowStory,
    getVortflowStoryTransitions, generateVortflowDescriptionPrompt,
    getMembers,
} from "@/api";
import { message } from "@openvort/vort-ui";
import { Plus, ArrowRight, Bot, Pencil } from "lucide-vue-next";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import AiAssistButton from "@/components/vort-biz/ai-assist-button/AiAssistButton.vue";

const router = useRouter();

// ===================== 类型定义 =====================

interface StoryItem {
    id: string;
    title: string;
    description?: string;
    state: string;
    priority: number;
    tags?: string[];
    collaborators?: string[];
    deadline?: string | null;
    project_id?: string;
    pm_id?: string | null;
    created_at?: string | null;
    owner?: string;
    workNo?: string;
}

type FilterParams = { page: number; size: number; state: string; priority: string; keyword: string; project_id: string };

// ===================== 状态选项 =====================

const stateOptions = [
    { label: "全部", value: "" },
    { label: "待确认", value: "draft" },
    { label: "设计中", value: "designing" },
    { label: "开发中", value: "developing" },
    { label: "开发完成", value: "developed" },
    { label: "测试中", value: "testing" },
    { label: "已发布", value: "released" },
    { label: "已关闭", value: "closed" },
];

const demandStatusFilterOptions = [
    { label: "已取消", value: "已取消", icon: "✕", iconClass: "text-red-500" },
    { label: "意向", value: "意向", icon: "○", iconClass: "text-slate-500" },
    { label: "暂搁置", value: "暂搁置", icon: "⌛", iconClass: "text-slate-400" },
    { label: "设计中", value: "设计中", icon: "✎", iconClass: "text-indigo-500" },
    { label: "开发中", value: "开发中", icon: "◔", iconClass: "text-blue-500" },
    { label: "开发完成", value: "开发完成", icon: "✓", iconClass: "text-cyan-600" },
    { label: "测试完成", value: "测试完成", icon: "✓", iconClass: "text-violet-600" },
    { label: "待发布", value: "待发布", icon: "◌", iconClass: "text-amber-600" },
    { label: "发布完成", value: "发布完成", icon: "✓", iconClass: "text-emerald-600" },
    { label: "已完成", value: "已完成", icon: "✓", iconClass: "text-emerald-700" },
];

const stateBackendToDisplay: Record<string, string> = {
    draft: "待确认", designing: "设计中", developing: "开发中", developed: "开发完成",
    testing: "测试中", released: "发布完成", closed: "已完成", rejected: "已取消",
    intake: "意向", review: "意向", pm_refine: "设计中", design: "设计中",
    breakdown: "开发中", dev_assign: "开发中", in_progress: "开发中", bugfix: "开发中",
    done: "已完成",
};

const displayToStateBackend: Record<string, string[]> = {
    "已取消": ["rejected"],
    "意向": ["intake", "review"],
    "暂搁置": ["rejected"],
    "设计中": ["pm_refine", "design"],
    "开发中": ["breakdown", "dev_assign", "in_progress", "bugfix"],
    "开发完成": ["developed"],
    "测试完成": ["testing"],
    "待发布": ["released"],
    "发布完成": ["released"],
    "已完成": ["done", "closed"],
};

const stateColorMap: Record<string, string> = {
    draft: "default", designing: "purple", developing: "blue", developed: "cyan",
    testing: "orange", released: "green", closed: "default", rejected: "red",
    intake: "default", review: "default", pm_refine: "purple", design: "purple",
    breakdown: "blue", dev_assign: "blue", in_progress: "blue", bugfix: "blue", done: "green",
};

const priorityOptions = [
    { label: "全部", value: "" },
    { label: "紧急", value: "1" },
    { label: "高", value: "2" },
    { label: "中", value: "3" },
    { label: "低", value: "4" },
];

const priorityColorMap: Record<string, string> = {
    "1": "red", "2": "orange", "3": "default", "4": "default", "urgent": "red", "high": "orange", "medium": "default", "low": "default", "none": "default",
};

const priorityLabelMap: Record<string, string> = {
    "1": "紧急", "2": "高", "3": "中", "4": "低", urgent: "紧急", high: "高", medium: "中", low: "低", none: "无",
};

const stateLabel = (val: string) => stateBackendToDisplay[val] || val;
const displayStatusLabel = (val: string) => demandStatusFilterOptions.find(o => o.value === val)?.label || val;

// ===================== 成员数据 =====================

interface MemberOption { id: string; name: string; avatarUrl?: string }

const members = ref<MemberOption[]>([]);
const memberGroups = ref<Array<{ label: string; members: string[] }>>([]);
const loadMembers = async () => {
    try {
        const res = await getMembers();
        const list = ((res as any)?.members || []) as any[];
        members.value = list.map(m => ({ id: m.id, name: m.name, avatarUrl: m.avatar_url }));
        const groupMap = new Map<string, string[]>();
        list.forEach(m => {
            const group = m.dept || "其他";
            if (!groupMap.has(group)) groupMap.set(group, []);
            groupMap.get(group)!.push(m.name);
        });
        memberGroups.value = Array.from(groupMap.entries()).map(([label, members]) => ({ label, members }));
    } catch { /* silent */ }
};
loadMembers();

const getMemberNameById = (id: string) => members.value.find(m => m.id === id)?.name || "";
const getMemberIdByName = (name: string) => members.value.find(m => m.name === name)?.id || "";

// ===================== 数据加载 =====================

const projects = ref<{ id: string; name: string }[]>([]);
const loadProjects = async () => {
    try {
        const res = await getVortflowProjects();
        projects.value = ((res as any) || []).map((p: any) => ({ id: p.id, name: p.name }));
    } catch { /* silent */ }
};
loadProjects();

const fetchStories = async (params: FilterParams) => {
    const res = await getVortflowStories({
        project_id: params.project_id || undefined,
        state: params.state || undefined,
        priority: params.priority ? Number(params.priority) : undefined,
        keyword: params.keyword,
        page: params.page,
        page_size: params.size,
    });
    const items = ((res as any).items || []) as any[];
    return {
        records: items.map((item, idx) => ({
            id: item.id,
            title: item.title,
            description: item.description,
            state: item.state,
            priority: item.priority,
            tags: item.tags || [],
            collaborators: item.collaborators || [],
            deadline: item.deadline,
            project_id: item.project_id,
            pm_id: item.pm_id,
            created_at: item.created_at,
            workNo: `#${String(item.id).replace(/-/g, "").slice(0, 6).toUpperCase().padEnd(6, "X")}`,
            owner: getMemberNameById(item.pm_id || ""),
        })),
        total: (res as any).total || 0
    };
};

const {
    listData, loading, total, filterParams, showPagination, rowSelection,
    loadData, onSearchSubmit, resetParams, deleteRow
} = useCrudPage<StoryItem, FilterParams>({
    api: fetchStories,
    defaultParams: { page: 1, size: 20, state: "", priority: "", keyword: "", project_id: "" },
    deleteApi: (data) => deleteVortflowStory(data.id),
});

// ===================== 行内编辑状态 =====================

const tagsModel = reactive<Record<string, string[]>>({});
const openTagFor = ref<string | null>(null);
const tagKeyword = ref("");
const availableTags = ["客户需求", "演示站", "运营需求", "待开会确认", "已发布", "高优先", "稳定性", "UI优化"];

const filteredTagOptions = computed(() => {
    const kw = tagKeyword.value.trim().toLowerCase();
    if (!kw) return availableTags;
    return availableTags.filter(t => t.toLowerCase().includes(kw));
});

const getRowTags = (record: StoryItem, text?: string): string[] => {
    return tagsModel[record.id] || text || record.tags || [];
};

const toggleTagMenu = (id: string) => {
    openTagFor.value = openTagFor.value !== id ? id : null;
    tagKeyword.value = "";
};

const toggleTagOption = async (record: StoryItem, tag: string, text?: string) => {
    const current = getRowTags(record, text);
    const idx = current.indexOf(tag);
    const newTags = idx >= 0 ? current.filter(t => t !== tag) : [...current, tag];
    tagsModel[record.id] = newTags;
};

const finishTagEdit = (record: StoryItem) => {
    const tags = tagsModel[record.id];
    if (!tags) return;
    try {
        updateVortflowStory(record.id, { tags });
        message.success("标签已更新");
        openTagFor.value = null;
    } catch (e: any) {
        message.error(e?.message || "更新失败");
    }
};

// ===================== 行内状态编辑 =====================

const openStatusFor = ref<string | null>(null);
const rowStatusKeyword = ref("");

const displayStatusOptions = demandStatusFilterOptions;

const filteredRowStatusOptions = computed(() => {
    const kw = rowStatusKeyword.value.trim();
    if (!kw) return displayStatusOptions;
    return displayStatusOptions.filter(x => x.label.includes(kw));
});

const toggleRowStatusMenu = (record: StoryItem) => {
    if (openStatusFor.value === record.id) {
        openStatusFor.value = null;
        rowStatusKeyword.value = "";
    } else {
        openStatusFor.value = record.id;
        rowStatusKeyword.value = "";
    }
};

const getRowDisplayStatus = (record: StoryItem): string => {
    return stateBackendToDisplay[record.state] || record.state;
};

const selectRowStatus = async (record: StoryItem, displayStatus: string) => {
    const states = displayToStateBackend[displayStatus];
    if (!states || states.length === 0) return;
    const targetState = states[0];
    try {
        await transitionVortflowStory(record.id, targetState);
        message.success("状态已更新");
        openStatusFor.value = null;
        rowStatusKeyword.value = "";
        loadData();
    } catch (e: any) {
        message.error(e?.message || "状态更新失败");
    }
};

// ===================== 行内优先级编辑 =====================

const openPriorityFor = ref<string | null>(null);

const getRowPriority = (record: StoryItem): string => {
    return String(record.priority || "4");
};

const togglePriorityMenu = (id: string) => {
    openPriorityFor.value = openPriorityFor.value !== id ? id : null;
};

const selectPriority = async (record: StoryItem, value: string) => {
    try {
        await updateVortflowStory(record.id, { priority: Number(value) });
        message.success("优先级已更新");
        openPriorityFor.value = null;
        loadData();
    } catch (e: any) {
        message.error(e?.message || "更新失败");
    }
};

// ===================== 行内负责人编辑 =====================

const openOwnerFor = ref<string | null>(null);
const ownerKeyword = ref("");

const filteredOwnerGroups = computed(() => {
    const kw = ownerKeyword.value.trim();
    if (!kw) return memberGroups.value;
    return memberGroups.value
        .map(g => ({ ...g, members: g.members.filter(m => m.includes(kw)) }))
        .filter(g => g.members.length > 0);
});

const toggleRowOwnerMenu = (id: string) => {
    if (openOwnerFor.value === id) {
        openOwnerFor.value = null;
        ownerKeyword.value = "";
    } else {
        openOwnerFor.value = id;
        ownerKeyword.value = "";
    }
};

const setRowOwner = async (record: StoryItem, name: string) => {
    const memberId = name ? getMemberIdByName(name) : "";
    if (name && !memberId) {
        message.error("未找到该成员");
        return;
    }
    try {
        await updateVortflowStory(record.id, { pm_id: memberId || null });
        message.success("负责人已更新");
        openOwnerFor.value = null;
        ownerKeyword.value = "";
        loadData();
    } catch (e: any) {
        message.error(e?.message || "更新失败");
    }
};

// ===================== 抽屉操作 =====================

const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<StoryItem>>({});
const formRef = ref();
const formLoading = ref(false);
const { takeSnapshot, confirmClose } = useDirtyCheck(currentRow);

const storyValidationSchema = z.object({
    project_id: z.string().min(1, "请选择所属项目"),
    title: z.string().min(1, "需求标题不能为空"),
    priority: z.string().optional().or(z.literal("")),
    deadline: z.string().optional().or(z.literal("")),
    description: z.string().optional(),
});

const handleAdd = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增需求";
    currentRow.value = { priority: 3, project_id: projects.value[0]?.id || "", tags: [], collaborators: [] };
    drawerVisible.value = true;
    takeSnapshot();
};

const handleEdit = (row: StoryItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑需求";
    currentRow.value = { ...row, deadline: row.deadline ? row.deadline.split("T")[0] : "" };
    drawerVisible.value = true;
    takeSnapshot();
};

const handleView = (row: StoryItem) => {
    drawerMode.value = "view";
    drawerTitle.value = "需求详情";
    currentRow.value = { ...row };
    drawerVisible.value = true;
    loadTransitions(row.id);
};

const handleSave = async () => {
    try { await formRef.value?.validate(); } catch { return; }
    const r = currentRow.value;
    formLoading.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVortflowStory({
                project_id: r.project_id!,
                title: r.title!,
                description: r.description,
                priority: r.priority ? Number(r.priority) : undefined,
                tags: r.tags,
                collaborators: r.collaborators,
                deadline: r.deadline || undefined,
            });
            message.success("创建成功");
        } else {
            await updateVortflowStory(r.id!, {
                title: r.title,
                description: r.description,
                priority: r.priority ? Number(r.priority) : undefined,
                tags: r.tags,
                collaborators: r.collaborators,
                deadline: r.deadline || undefined,
            });
            message.success("更新成功");
        }
        drawerVisible.value = false;
        loadData();
    } catch (e: any) {
        message.error(e?.message || "操作失败");
    } finally {
        formLoading.value = false;
    }
};

const handleDelete = async (row: StoryItem) => {
    const success = await deleteRow(row);
    if (success) {
        if (drawerVisible.value && currentRow.value.id === row.id) {
            drawerVisible.value = false;
        }
    }
};

// AI 生成描述
async function handleAiGenerateDescription() {
    if (!currentRow.value.title?.trim()) {
        message.warning("请先输入需求标题");
        return;
    }
    try {
        const res: any = await generateVortflowDescriptionPrompt("story", "", currentRow.value.title);
        if (res?.prompt) {
            drawerVisible.value = false;
            router.push({ name: "chat", query: { prompt: res.prompt } });
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "生成失败");
    }
}

// ===================== 状态流转 =====================

const allowedTransitions = ref<string[]>([]);
const transitionLoading = ref(false);

const loadTransitions = async (id: string) => {
    try {
        const res = await getVortflowStoryTransitions(id);
        allowedTransitions.value = (res as any).transitions || [];
    } catch { allowedTransitions.value = []; }
};

const handleTransition = async (row: StoryItem, targetState: string) => {
    transitionLoading.value = true;
    try {
        await transitionVortflowStory(row.id, targetState);
        loadData();
        if (drawerVisible.value && currentRow.value.id === row.id) {
            currentRow.value.state = targetState;
            loadTransitions(row.id);
        }
    } catch (e: any) {
        message.error(e?.message || "状态流转失败");
    } finally {
        transitionLoading.value = false;
    }
};

// ===================== 详情抽屉标签页 =====================

const detailActiveTab = ref<"detail" | "worklog" | "related">("detail");
const detailDescEditing = ref(false);
const detailDescDraft = ref("");

const openDetailDescEditor = () => {
    detailDescDraft.value = currentRow.value.description || "";
    detailDescEditing.value = true;
};

const cancelDetailDescEditor = () => {
    detailDescEditing.value = false;
    detailDescDraft.value = "";
};

const saveDetailDescEditor = async () => {
    try {
        await updateVortflowStory(currentRow.value.id!, { description: detailDescDraft.value });
        currentRow.value.description = detailDescDraft.value;
        message.success("描述已保存");
        detailDescEditing.value = false;
    } catch (e: any) {
        message.error(e?.message || "保存失败");
    }
};

loadData();
</script>

<template>
    <div class="space-y-4">
        <!-- Search -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">需求列表</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增需求
                </vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 flex-wrap">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search
                        v-model="filterParams.keyword"
                        placeholder="搜索需求..."
                        allow-clear
                        class="flex-1 sm:w-[200px]"
                        @search="onSearchSubmit"
                        @keyup.enter="onSearchSubmit"
                    />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">项目</span>
                    <vort-select
                        v-model="filterParams.project_id"
                        placeholder="全部"
                        allow-clear
                        class="flex-1 sm:w-[140px]"
                        @change="onSearchSubmit"
                    >
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select
                        v-model="filterParams.state"
                        placeholder="全部"
                        allow-clear
                        class="flex-1 sm:w-[120px]"
                        @change="onSearchSubmit"
                    >
                        <vort-select-option v-for="opt in stateOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">优先级</span>
                    <vort-select
                        v-model="filterParams.priority"
                        placeholder="全部"
                        allow-clear
                        class="flex-1 sm:w-[100px]"
                        @change="onSearchSubmit"
                    >
                        <vort-select-option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>
        </div>

        <!-- Table -->
        <div class="bg-white rounded-xl p-4">
            <vort-table :data-source="listData" :loading="loading" :pagination="false" :row-selection="rowSelection">
                <vort-table-column label="编号" :width="110" fixed="left">
                    <template #default="{ row }">
                        <span class="text-sm font-mono text-gray-500">{{ row.workNo }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="标题" :width="240" fixed="left">
                    <template #default="{ row }">
                        <a class="text-blue-600 hover:text-blue-800 cursor-pointer" @click="handleView(row)">{{ row.title }}</a>
                    </template>
                </vort-table-column>
                <vort-table-column label="状态" :width="120">
                    <template #default="{ row }">
                        <Popover
                            :open="openStatusFor === row.id"
                            trigger="click"
                            placement="bottomLeft"
                            :arrow="false"
                            @update:open="(open) => { if (!open && openStatusFor === row.id) openStatusFor = null; }"
                        >
                            <template #trigger>
                                <vort-button variant="text" class="status-edit-trigger" @click.stop="toggleRowStatusMenu(row.id)">
                                    <span class="status-badge table-status-badge" :class="stateColorMap[row.state] ? `bg-${stateColorMap[row.state]}-50 text-${stateColorMap[row.state]}-600 border-${stateColorMap[row.state]}-100` : ''">
                                        {{ getRowDisplayStatus(row) }}
                                    </span>
                                </vort-button>
                            </template>
                            <template #content>
                                <div class="w-[240px] p-3" @click.stop>
                                    <div class="mb-2">
                                        <vort-input v-model="rowStatusKeyword" placeholder="搜索..." size="small" class="w-full" />
                                    </div>
                                    <div class="max-h-[220px] overflow-y-auto pr-1">
                                        <vort-button
                                            v-for="opt in filteredRowStatusOptions"
                                            :key="opt.value"
                                            class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                            variant="text"
                                            :class="getRowDisplayStatus(row) === opt.value ? 'bg-slate-100' : ''"
                                            @click="selectRowStatus(row, opt.value)"
                                        >
                                            <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                                <span v-if="getRowDisplayStatus(row) === opt.value">✓</span>
                                            </span>
                                            <span class="text-[14px] leading-none w-4 text-center" :class="opt.iconClass">{{ opt.icon }}</span>
                                            <span class="text-sm text-gray-700">{{ opt.label }}</span>
                                        </vort-button>
                                    </div>
                                </div>
                            </template>
                        </Popover>
                    </template>
                </vort-table-column>
                <vort-table-column label="负责人" :width="160">
                    <template #default="{ row }">
                        <Popover
                            :open="openOwnerFor === row.id"
                            trigger="click"
                            placement="bottomLeft"
                            :arrow="false"
                            @update:open="(open) => { if (!open && openOwnerFor === row.id) openOwnerFor = null; }"
                        >
                            <template #trigger>
                                <vort-button variant="text" class="w-full text-left" @click.stop="toggleRowOwnerMenu(row.id)">
                                    <span class="text-sm text-gray-700">{{ row.owner || '未指派' }}</span>
                                </vort-button>
                            </template>
                            <template #content>
                                <div class="w-[260px] p-3" @click.stop>
                                    <div class="mb-2">
                                        <vort-input v-model="ownerKeyword" placeholder="搜索成员..." size="small" class="w-full" />
                                    </div>
                                    <div class="max-h-[280px] overflow-y-auto -mx-3">
                                        <div v-for="group in filteredOwnerGroups" :key="group.label" class="mb-1">
                                            <vort-button class="w-full h-8 px-3 bg-slate-50 flex items-center justify-between text-left" variant="text">
                                                <span class="text-xs text-gray-500">{{ group.label }}（{{ group.members.length }}）</span>
                                            </vort-button>
                                            <div v-for="name in group.members" :key="name" class="owner-row">
                                                <span class="text-sm text-gray-700">{{ name }}</span>
                                                <vort-button size="small" variant="text" :class="row.owner === name ? 'text-blue-600' : 'text-gray-400'" @click="setRowOwner(row, name)">
                                                    {{ row.owner === name ? '当前负责人' : '设为负责人' }}
                                                </vort-button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </Popover>
                    </template>
                </vort-table-column>
                <vort-table-column label="优先级" :width="100">
                    <template #default="{ row }">
                        <Popover
                            :open="openPriorityFor === row.id"
                            trigger="click"
                            placement="bottomLeft"
                            :arrow="false"
                            @update:open="(open) => { if (!open && openPriorityFor === row.id) openPriorityFor = null; }"
                        >
                            <template #trigger>
                                <vort-button variant="text" class="w-full text-left" @click.stop="togglePriorityMenu(row.id)">
                                    <span class="priority-pill" :class="`priority-${getRowPriority(row)}`">
                                        {{ priorityLabelMap[getRowPriority(row)] || '无' }}
                                    </span>
                                </vort-button>
                            </template>
                            <template #content>
                                <div class="p-2" @click.stop>
                                    <vort-button
                                        v-for="opt in priorityOptions.filter(o => o.value)"
                                        :key="opt.value"
                                        variant="text"
                                        class="w-full justify-start h-9"
                                        :class="getRowPriority(row) === opt.value ? 'bg-slate-100' : ''"
                                        @click="selectPriority(row, opt.value)"
                                    >
                                        <span class="priority-pill" :class="`priority-${opt.value}`">{{ opt.label }}</span>
                                    </vort-button>
                                </div>
                            </template>
                        </Popover>
                    </template>
                </vort-table-column>
                <vort-table-column label="标签" :width="180">
                    <template #default="{ row }">
                        <Popover
                            :open="openTagFor === row.id"
                            trigger="click"
                            placement="bottomLeft"
                            :arrow="false"
                            @update:open="(open) => { if (!open && openTagFor === row.id) openTagFor = null; }"
                        >
                            <template #trigger>
                                <vort-button variant="text" class="w-full text-left" @click.stop="toggleTagMenu(row.id)">
                                    <div class="flex items-center gap-1 flex-nowrap whitespace-nowrap overflow-hidden">
                                        <template v-for="tag in (getRowTags(row) || []).slice(0, 3)" :key="tag">
                                            <span class="px-1.5 py-0.5 rounded text-xs text-white inline-block bg-blue-500">{{ tag }}</span>
                                        </template>
                                        <span v-if="(getRowTags(row) || []).length > 3" class="text-gray-400 font-medium text-sm">+{{ (getRowTags(row) || []).length - 3 }}</span>
                                        <span v-if="!(getRowTags(row) || []).length" class="text-gray-400 text-sm">-</span>
                                    </div>
                                </vort-button>
                            </template>
                            <template #content>
                                <div class="w-[240px] p-3" @click.stop>
                                    <div class="mb-2">
                                        <vort-input v-model="tagKeyword" placeholder="搜索..." size="small" class="w-full" />
                                    </div>
                                    <div class="max-h-[200px] overflow-y-auto pr-1">
                                        <vort-button
                                            v-for="tag in filteredTagOptions"
                                            :key="tag"
                                            class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                            variant="text"
                                            @click="toggleTagOption(row, tag)"
                                        >
                                            <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                                <span v-if="getRowTags(row).includes(tag)">✓</span>
                                            </span>
                                            <span class="w-5 h-5 rounded-full bg-blue-500" />
                                            <span class="text-sm text-gray-700">{{ tag }}</span>
                                        </vort-button>
                                    </div>
                                    <div class="mt-2 flex justify-end">
                                        <vort-button size="small" variant="primary" @click="finishTagEdit(row)">完成</vort-button>
                                    </div>
                                </div>
                            </template>
                        </Popover>
                    </template>
                </vort-table-column>
                <vort-table-column label="截止日期" :width="120">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-500">{{ row.deadline ? row.deadline.split("T")[0] : "-" }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="操作" :width="140" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-1 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleView(row)">详情</a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除该需求？" @confirm="handleDelete(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>

            <div v-if="showPagination" class="flex justify-end mt-4">
                <vort-pagination
                    v-model:current="filterParams.page"
                    v-model:page-size="filterParams.size"
                    :total="total"
                    show-total-info
                    show-size-changer
                    @change="loadData"
                />
            </div>
        </div>

        <!-- Drawer -->
        <vort-drawer
            :open="drawerVisible"
            :title="drawerTitle"
            :width="900"
            @update:open="(val: boolean) => { if (!val && drawerMode !== 'view') { confirmClose(() => { drawerVisible = false }) } else { drawerVisible = val } }"
        >
            <!-- View -->
            <div v-if="drawerMode === 'view'">
                <!-- Header -->
                <div class="flex items-center gap-3 mb-4">
                    <span class="work-type-icon-demand text-2xl">≡</span>
                    <span class="work-no-display">{{ currentRow.workNo }}</span>
                    <vort-tag :color="stateColorMap[currentRow.state!] || 'default'">{{ getRowDisplayStatus(currentRow) }}</vort-tag>
                </div>

                <h2 class="text-xl font-medium text-gray-800 mb-2">{{ currentRow.title }}</h2>
                <p class="text-sm text-gray-500 mb-4">
                    {{ currentRow.owner || "未指派" }}，创建于 {{ currentRow.created_at ? currentRow.created_at.split("T")[0] : "-" }}
                </p>

                <!-- Tabs -->
                <div class="bug-detail-tabs mb-4">
                    <button :class="{ active: detailActiveTab === 'detail' }" @click="detailActiveTab = 'detail'">详情</button>
                    <button :class="{ active: detailActiveTab === 'worklog' }" @click="detailActiveTab = 'worklog'">工作日志</button>
                    <button :class="{ active: detailActiveTab === 'related' }" @click="detailActiveTab = 'related'">关联任务</button>
                </div>

                <div v-if="detailActiveTab === 'detail'">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                        <div>
                            <span class="text-sm text-gray-400">项目</span>
                            <div class="text-sm text-gray-800 mt-1">{{ projects.find(p => p.id === currentRow.project_id)?.name || "-" }}</div>
                        </div>
                        <div>
                            <span class="text-sm text-gray-400">负责人</span>
                            <div class="text-sm text-gray-800 mt-1">{{ currentRow.owner || "未指派" }}</div>
                        </div>
                        <div>
                            <span class="text-sm text-gray-400">优先级</span>
                            <div class="mt-1">
                                <vort-tag :color="priorityColorMap[String(currentRow.priority)] || 'default'">
                                    {{ priorityLabelMap[String(currentRow.priority)] || "-" }}
                                </vort-tag>
                            </div>
                        </div>
                        <div>
                            <span class="text-sm text-gray-400">截止日期</span>
                            <div class="text-sm text-gray-800 mt-1">{{ currentRow.deadline ? currentRow.deadline.split("T")[0] : "-" }}</div>
                        </div>
                        <div v-if="currentRow.tags?.length" class="sm:col-span-2">
                            <span class="text-sm text-gray-400">标签</span>
                            <div class="flex flex-wrap gap-1 mt-1">
                                <span v-for="tag in currentRow.tags" :key="tag" class="px-2 py-0.5 rounded text-xs text-white bg-blue-500">{{ tag }}</span>
                            </div>
                        </div>
                        <div v-if="currentRow.collaborators?.length" class="sm:col-span-2">
                            <span class="text-sm text-gray-400">协作者</span>
                            <div class="flex flex-wrap gap-1 mt-1">
                                <span v-for="c in currentRow.collaborators" :key="c" class="text-sm text-gray-600">{{ c }}</span>
                            </div>
                        </div>
                    </div>

                    <div class="bug-detail-desc">
                        <div class="bug-detail-desc-head">
                            <h4>描述</h4>
                            <vort-button variant="text" size="small" @click="openDetailDescEditor">
                                <Pencil :size="14" />
                            </vort-button>
                        </div>
                        <template v-if="detailDescEditing">
                            <VortEditor v-model="detailDescDraft" placeholder="请输入描述内容..." min-height="200px" />
                            <div class="flex justify-end gap-2 mt-2">
                                <vort-button @click="cancelDetailDescEditor">取消</vort-button>
                                <vort-button variant="primary" @click="saveDetailDescEditor">保存</vort-button>
                            </div>
                        </template>
                        <template v-else>
                            <div v-if="(currentRow.description || '').trim()" class="bug-detail-desc-content">
                                <MarkdownView :content="currentRow.description || ''" />
                            </div>
                            <div v-else class="text-gray-400">-</div>
                        </template>
                    </div>
                </div>

                <div v-if="detailActiveTab === 'worklog'" class="text-gray-400 text-center py-8">
                    暂无工作日志
                </div>

                <div v-if="detailActiveTab === 'related'" class="text-gray-400 text-center py-8">
                    暂无关联任务
                </div>

                <!-- Transitions -->
                <div v-if="allowedTransitions.length" class="border-t pt-4 mt-4">
                    <span class="text-sm text-gray-500 mb-2 block">状态流转</span>
                    <div class="flex flex-wrap gap-2">
                        <vort-button
                            v-for="t in allowedTransitions"
                            :key="t"
                            size="small"
                            :loading="transitionLoading"
                            @click="handleTransition(currentRow as StoryItem, t)"
                        >
                            <ArrowRight :size="12" class="mr-1" /> {{ stateBackendToDisplay[t] || t }}
                        </vort-button>
                    </div>
                </div>

                <!-- AI -->
                <div class="border-t pt-4 mt-4">
                    <span class="text-sm text-gray-500 mb-2 block">AI 辅助</span>
                    <AiAssistButton
                        :prompt="`请帮我实现需求「${currentRow.title}」，描述：${currentRow.description || '无'}。Story ID: ${currentRow.id}`"
                        label="AI 编码"
                    />
                </div>
            </div>

            <!-- Edit / Add -->
            <template v-else>
                <vort-form ref="formRef" :model="currentRow" :rules="storyValidationSchema" label-width="80px">
                    <vort-form-item label="所属项目" name="project_id" required has-feedback>
                        <vort-select v-model="currentRow.project_id" placeholder="选择项目" :disabled="drawerMode === 'edit'" class="w-full">
                            <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="标题" name="title" required has-feedback>
                        <vort-input v-model="currentRow.title" placeholder="请输入需求标题" />
                    </vort-form-item>
                    <vort-form-item label="优先级" name="priority">
                        <vort-select v-model="currentRow.priority" class="w-full">
                            <vort-select-option :value="1">紧急</vort-select-option>
                            <vort-select-option :value="2">高</vort-select-option>
                            <vort-select-option :value="3">中</vort-select-option>
                            <vort-select-option :value="4">低</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="截止日期" name="deadline">
                        <vort-date-picker v-model="currentRow.deadline" value-format="YYYY-MM-DD" placeholder="请选择截止日期" class="w-full" />
                    </vort-form-item>
                    <vort-form-item label="描述" name="description">
                        <div class="space-y-2">
                            <VortEditor v-model="currentRow.description" placeholder="请输入需求描述" min-height="160px" />
                            <div class="flex justify-end">
                                <vort-button size="small" @click="handleAiGenerateDescription">
                                    <Bot :size="12" class="mr-1" /> AI 助手创建
                                </vort-button>
                            </div>
                        </div>
                    </vort-form-item>
                </vort-form>
                <div class="flex justify-end gap-3 mt-6">
                    <vort-button @click="confirmClose(() => { drawerVisible = false })">取消</vort-button>
                    <vort-button variant="primary" :loading="formLoading" @click="handleSave">确定</vort-button>
                </div>
            </template>
        </vort-drawer>
    </div>
</template>

<style scoped>
.work-type-icon-demand {
    font-size: 20px;
    color: #3b82f6;
}
.work-no-display {
    font-family: monospace;
    font-size: 14px;
    color: #6b7280;
}
.bug-detail-tabs {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 8px;
}
.bug-detail-tabs button {
    padding: 6px 16px;
    font-size: 14px;
    color: #6b7280;
    background: none;
    border: none;
    cursor: pointer;
    border-radius: 4px;
}
.bug-detail-tabs button:hover {
    background: #f3f4f6;
}
.bug-detail-tabs button.active {
    color: #3b82f6;
    background: #eff6ff;
}
.bug-detail-desc-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.bug-detail-desc-head h4 {
    font-size: 14px;
    font-weight: 500;
    color: #6b7280;
}
.bug-detail-desc-content {
    padding: 12px;
    background: #f9fafb;
    border-radius: 8px;
}
.status-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    border: 1px solid;
}
.priority-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
}
.priority-1, .priority-urgent { background: #fef2f2; color: #dc2626; border-color: #fecaca; }
.priority-2, .priority-high { background: #fff7ed; color: #ea580c; border-color: #fed7aa; }
.priority-3, .priority-medium { background: #f9fafb; color: #6b7280; border-color: #e5e7eb; }
.priority-4, .priority-low, .priority-none { background: #f9fafb; color: #9ca3af; border-color: #e5e7eb; }
.owner-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-bottom: 1px solid #f3f4f6;
}
.owner-row:last-child {
    border-bottom: none;
}
</style>

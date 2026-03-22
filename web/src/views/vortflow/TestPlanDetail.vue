<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
    Plus, Search, ChevronRight, ChevronDown, FolderOpen, Folder,
    Ellipsis, CheckCircle, XCircle, AlertCircle, SkipForward, Bug, ChevronsUpDown,
} from "lucide-vue-next";
import { message, Dropdown, DropdownMenuItem } from "@/components/vort";
import { useVortFlowStore } from "@/stores";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import WorkItemCreate from "./work-item/WorkItemCreate.vue";
import TestPlanEditDialog from "./components/TestPlanEditDialog.vue";
import TestPlanAddCasesDialog from "./components/TestPlanAddCasesDialog.vue";
import {
    getVortflowTestPlan,
    getVortflowTestPlanCases,
    removeVortflowTestPlanCase,
    addVortflowTestPlanExecution,
    updateVortflowTestPlan,
    getVortflowTestModules,
    getVortflowIterations,
    getVortflowVersions,
    createVortflowBug,
    createVortflowTestCaseLink,
    getVortflowTestPlans,
} from "@/api";
import type { NewBugForm } from "@/components/vort-biz/work-item/WorkItemTable.types";

const route = useRoute();
const router = useRouter();
const vortFlowStore = useVortFlowStore();
const {
    getAvatarBg, getAvatarLabel, getMemberAvatarUrl,
    loadMemberOptions, getMemberIdByName,
} = useWorkItemCommon();

const planId = computed(() => route.params.id as string);
const plan = ref<any>({});
const planLoading = ref(true);
const activeTab = ref("cases");

const statusLabels: Record<string, string> = {
    planning: "待开始",
    in_progress: "进行中",
    completed: "已完成",
    suspended: "已挂起",
};
const statusColorMap: Record<string, string> = {
    in_progress: "processing",
    completed: "green",
    suspended: "default",
    planning: "default",
};

const caseTypeLabels: Record<string, string> = {
    functional: "功能测试",
    performance: "性能测试",
    api: "接口测试",
    ui: "UI 测试",
    security: "安全测试",
};
const priorityLabels: Record<number, string> = { 0: "P0", 1: "P1", 2: "P2", 3: "P3" };
const priorityColors: Record<number, string> = { 0: "red", 1: "red", 2: "orange", 3: "default" };

const resultIcons: Record<string, { icon: any; color: string; label: string }> = {
    passed: { icon: CheckCircle, color: "text-green-500", label: "通过" },
    blocked: { icon: AlertCircle, color: "text-orange-400", label: "受阻" },
    failed: { icon: XCircle, color: "text-red-500", label: "失败" },
    skipped: { icon: SkipForward, color: "text-blue-400", label: "跳过" },
};
const resultOptions = [
    { value: "passed", label: "通过", color: "text-green-500", icon: CheckCircle },
    { value: "blocked", label: "受阻", color: "text-orange-400", icon: AlertCircle },
    { value: "failed", label: "失败", color: "text-red-500", icon: XCircle },
    { value: "skipped", label: "跳过", color: "text-blue-400", icon: SkipForward },
];

// ============ Load Plan ============

const loadPlan = async () => {
    planLoading.value = true;
    try {
        const res = await getVortflowTestPlan(planId.value);
        if ((res as any).error) {
            message.error((res as any).error);
            return;
        }
        plan.value = res;
    } finally {
        planLoading.value = false;
    }
};

// ============ Plan Switcher ============

const planSwitcherOpen = ref(false);
const planSwitcherSearch = ref("");
const planSwitcherList = ref<{ id: string; title: string; status: string }[]>([]);

const filteredPlanList = computed(() => {
    const kw = planSwitcherSearch.value.trim().toLowerCase();
    if (!kw) return planSwitcherList.value;
    return planSwitcherList.value.filter(p => p.title.toLowerCase().includes(kw));
});

const loadPlanSwitcherList = async () => {
    const projectId = plan.value?.project_id;
    if (!projectId) return;
    const res = await getVortflowTestPlans({ project_id: projectId, page_size: 100 });
    planSwitcherList.value = ((res as any).items || []).map((p: any) => ({
        id: p.id, title: p.title, status: p.status,
    }));
};

const handleSwitchPlan = (id: string) => {
    planSwitcherOpen.value = false;
    planSwitcherSearch.value = "";
    if (id !== planId.value) {
        router.push(`/vortflow/test-plans/${id}`);
    }
};

// ============ Module Tree ============

interface RawModule {
    id: string;
    name: string;
    parent_id: string | null;
}

interface FlatNode {
    id: string;
    name: string;
    parent_id: string | null;
    depth: number;
    hasChildren: boolean;
    expanded: boolean;
}

const rawModules = ref<RawModule[]>([]);
const expandedModuleIds = ref<Set<string>>(new Set());
const selectedModuleId = ref("");
const moduleSearch = ref("");
const showModuleSearch = ref(false);

const flatNodes = computed<FlatNode[]>(() => {
    const map = new Map<string, RawModule>();
    const childMap = new Map<string, string[]>();
    for (const m of rawModules.value) {
        map.set(m.id, m);
        const pid = m.parent_id || "__root__";
        if (!childMap.has(pid)) childMap.set(pid, []);
        childMap.get(pid)!.push(m.id);
    }
    const kw = moduleSearch.value.trim().toLowerCase();
    const matchesSearch = (id: string): boolean => {
        if (!kw) return true;
        const mod = map.get(id);
        if (!mod) return false;
        if (mod.name.toLowerCase().includes(kw)) return true;
        return (childMap.get(id) || []).some((cid) => matchesSearch(cid));
    };
    const result: FlatNode[] = [];
    const walk = (parentId: string, depth: number) => {
        const children = childMap.get(parentId) || [];
        for (const id of children) {
            if (!matchesSearch(id)) continue;
            const mod = map.get(id)!;
            const hasChildren = (childMap.get(id) || []).length > 0;
            const expanded = kw ? true : expandedModuleIds.value.has(id);
            result.push({ id: mod.id, name: mod.name, parent_id: mod.parent_id, depth, hasChildren, expanded });
            if (expanded && hasChildren) walk(id, depth + 1);
        }
    };
    walk("__root__", 0);
    return result;
});

const loadModules = async () => {
    const projectId = plan.value?.project_id;
    if (!projectId) return;
    try {
        const res = await getVortflowTestModules({ project_id: projectId });
        rawModules.value = (res as any)?.items || [];
        const parentIds = new Set(rawModules.value.filter((m) => m.parent_id).map((m) => m.parent_id!));
        for (const pid of parentIds) expandedModuleIds.value.add(pid);
    } catch {
        rawModules.value = [];
    }
};

const toggleModuleExpand = (id: string) => {
    const next = new Set(expandedModuleIds.value);
    if (next.has(id)) next.delete(id); else next.add(id);
    expandedModuleIds.value = next;
};

const selectModule = (id: string) => {
    selectedModuleId.value = selectedModuleId.value === id ? "" : id;
    loadCases();
};

// ============ Plan Cases ============

const cases = ref<any[]>([]);
const casesLoading = ref(false);
const casesTotal = ref(0);
const caseKeyword = ref("");
const caseSortBy = ref("");

const loadCases = async () => {
    casesLoading.value = true;
    try {
        const res = await getVortflowTestPlanCases(planId.value, {
            module_id: selectedModuleId.value || undefined,
            keyword: caseKeyword.value || undefined,
            sort_by: caseSortBy.value || undefined,
        });
        cases.value = (res as any).items || [];
        casesTotal.value = (res as any).total || 0;
    } finally {
        casesLoading.value = false;
    }
};

const handleRemoveCase = async (planCaseId: string) => {
    await removeVortflowTestPlanCase(planId.value, planCaseId);
    message.success("已移除");
    loadCases();
    loadPlan();
};

// ============ Execution Result ============

const executionDropdownOpen = ref<Record<string, boolean>>({});

const handleAddExecution = async (planCaseId: string, result: string) => {
    await addVortflowTestPlanExecution(planId.value, planCaseId, { result });
    executionDropdownOpen.value[planCaseId] = false;
    loadCases();
    loadPlan();
};

const latestResultDisplay = (item: any) => {
    if (!item.latest_result) return null;
    return resultIcons[item.latest_result] || null;
};

// ============ Result distribution bar ============

const resultBarStyle = computed(() => {
    const t = plan.value?.total_cases || 0;
    if (!t) return { passed: "0%", failed: "0%", blocked: "0%", rest: "0%" };
    const p = plan.value;
    return {
        passed: `${(p.passed / t) * 100}%`,
        failed: `${(p.failed / t) * 100}%`,
        blocked: `${(p.blocked / t) * 100}%`,
        rest: `${(((t - p.passed - p.failed - p.blocked)) / t) * 100}%`,
    };
});

const resultPercent = computed(() => {
    const t = plan.value?.total_cases || 0;
    if (!t) return "0%";
    return `${Math.round(((plan.value?.executed_cases || 0) / t) * 100)}%`;
});

const resultDistDetail = computed(() => {
    const t = plan.value?.total_cases || 0;
    const pct = (n: number) => t ? `${((n / t) * 100).toFixed(2)}%` : "0%";
    const p = plan.value || {};
    const passed = p.passed || 0;
    const blocked = p.blocked || 0;
    const failed = p.failed || 0;
    const skipped = p.skipped || 0;
    const unexecuted = Math.max(0, t - passed - blocked - failed - skipped);
    return [
        { label: "通过", count: passed, pct: pct(passed), color: "text-green-500", bg: "bg-green-500", icon: CheckCircle },
        { label: "受阻", count: blocked, pct: pct(blocked), color: "text-orange-400", bg: "bg-orange-400", icon: AlertCircle },
        { label: "失败", count: failed, pct: pct(failed), color: "text-red-500", bg: "bg-red-500", icon: XCircle },
        { label: "跳过", count: skipped, pct: pct(skipped), color: "text-blue-400", bg: "bg-blue-400", icon: SkipForward },
        { label: "未执行", count: unexecuted, pct: pct(unexecuted), color: "text-gray-400", bg: "bg-gray-300", icon: null },
    ];
});

// ============ Edit dialog ============

const editDialogOpen = ref(false);
const editData = ref<any>(null);

const handleEditPlan = () => {
    editData.value = { ...plan.value };
    editDialogOpen.value = true;
};

const handleFinishPlan = async () => {
    await updateVortflowTestPlan(planId.value, { status: "completed" });
    message.success("已结束计划");
    loadPlan();
};

// ============ Add Cases Dialog ============

const addCasesDialogOpen = ref(false);

const handleAddCasesSaved = () => {
    loadCases();
    loadPlan();
};

// ============ File Bug ============

const fileBugDrawerOpen = ref(false);
const fileBugCaseRow = ref<any>(null);
const createWorkItemRef = ref<InstanceType<typeof WorkItemCreate> | null>(null);

const handleOpenFileBug = (row: any) => {
    fileBugCaseRow.value = row;
    fileBugDrawerOpen.value = true;
};

const handleSubmitFileBug = async () => {
    const formData = createWorkItemRef.value?.submit() as NewBugForm | null;
    if (!formData) return;
    const title = formData.title.trim();
    if (!title) { message.warning("请填写标题"); return; }
    try {
        const ownerId = getMemberIdByName(formData.owner) || undefined;
        const createdBug: any = await createVortflowBug({
            project_id: plan.value?.project_id || undefined,
            title,
            description: formData.description || "",
            severity: formData.priority === "urgent" ? 1 : formData.priority === "high" ? 2 : formData.priority === "medium" ? 3 : 4,
            assignee_id: ownerId,
            tags: [...formData.tags],
            collaborators: [...formData.collaborators],
        });
        const bugId = createdBug?.id;
        const testCaseId = fileBugCaseRow.value?.test_case_id;
        if (bugId && testCaseId) {
            try {
                await createVortflowTestCaseLink({
                    test_case_id: testCaseId,
                    entity_type: "bug",
                    entity_id: String(bugId),
                });
            } catch { /* link failed silently */ }
        }
        message.success("缺陷已创建并关联测试用例");
        fileBugDrawerOpen.value = false;
        fileBugCaseRow.value = null;
    } catch (e: any) {
        message.error(e?.message || "创建失败");
    }
};

const handleCancelFileBug = () => {
    fileBugDrawerOpen.value = false;
    fileBugCaseRow.value = null;
};

// ============ Link Iteration / Version ============

const iterationOptions = ref<{ id: string; name: string; status?: string }[]>([]);
const versionOptions = ref<{ id: string; name: string; stage?: string }[]>([]);
const iterLinkOpen = ref(false);
const verLinkOpen = ref(false);
const iterLinkSearch = ref("");
const verLinkSearch = ref("");

const filteredIterations = computed(() => {
    const kw = iterLinkSearch.value.trim().toLowerCase();
    if (!kw) return iterationOptions.value;
    return iterationOptions.value.filter(i => i.name.toLowerCase().includes(kw));
});

const filteredVersions = computed(() => {
    const kw = verLinkSearch.value.trim().toLowerCase();
    if (!kw) return versionOptions.value;
    return versionOptions.value.filter(v => v.name.toLowerCase().includes(kw));
});

const loadLinkOptions = async () => {
    const projectId = plan.value?.project_id;
    if (!projectId) return;
    const [iterRes, verRes] = await Promise.all([
        getVortflowIterations({ project_id: projectId, page_size: 100 }),
        getVortflowVersions({ project_id: projectId, page_size: 100 }),
    ]);
    iterationOptions.value = ((iterRes as any).items || []).map((i: any) => ({ id: i.id, name: i.name, status: i.status }));
    versionOptions.value = ((verRes as any).items || []).map((v: any) => ({ id: v.id, name: v.name, stage: v.stage }));
};

const handleLinkIteration = async (iterationId: string | null) => {
    await updateVortflowTestPlan(planId.value, { iteration_id: iterationId || "" });
    iterLinkOpen.value = false;
    iterLinkSearch.value = "";
    loadPlan();
};

const handleLinkVersion = async (versionId: string | null) => {
    await updateVortflowTestPlan(planId.value, { version_id: versionId || "" });
    verLinkOpen.value = false;
    verLinkSearch.value = "";
    loadPlan();
};

const iterStatusLabels: Record<string, string> = { planning: "待开始", active: "进行中", completed: "已结束" };
const verStageLabels: Record<string, string> = { dev: "开发环境", staging: "预发布", production: "生产环境", archived: "已归档" };

// ============ Init ============

onMounted(async () => {
    await loadMemberOptions();
    await loadPlan();
    await Promise.all([loadModules(), loadCases(), loadLinkOptions(), loadPlanSwitcherList()]);
});

watch(planId, async () => {
    await loadPlan();
    await Promise.all([loadModules(), loadCases()]);
});
</script>

<template>
    <div class="space-y-4">
        <!-- Header -->
        <div class="bg-white rounded-xl p-6">
            <vort-spin :spinning="planLoading">
                <div class="flex items-start justify-between mb-3">
                    <Dropdown v-model:open="planSwitcherOpen" trigger="click">
                        <h2 class="text-lg font-semibold text-gray-800 inline-flex items-center gap-1 cursor-pointer hover:text-blue-600 transition-colors">
                            {{ plan.title }}
                            <ChevronsUpDown :size="16" class="text-gray-400" />
                        </h2>
                        <template #overlay>
                            <div class="p-2 w-[280px]">
                                <vort-input-search
                                    v-model="planSwitcherSearch"
                                    placeholder="搜索测试计划..."
                                    allow-clear
                                    size="small"
                                    class="mb-2"
                                />
                                <div class="max-h-[300px] overflow-y-auto">
                                    <div
                                        v-for="item in filteredPlanList"
                                        :key="item.id"
                                        class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 flex items-center justify-between"
                                        :class="item.id === planId ? 'bg-blue-50 text-blue-600 font-medium' : 'text-gray-700'"
                                        @click="handleSwitchPlan(item.id)"
                                    >
                                        <span class="truncate mr-2">{{ item.title }}</span>
                                        <vort-tag :color="statusColorMap[item.status] || 'default'" size="small">
                                            {{ statusLabels[item.status] || item.status }}
                                        </vort-tag>
                                    </div>
                                    <div v-if="!filteredPlanList.length" class="px-3 py-4 text-sm text-gray-400 text-center">
                                        无匹配项
                                    </div>
                                </div>
                            </div>
                        </template>
                    </Dropdown>
                    <div class="flex items-center gap-2">
                        <vort-button v-if="plan.status !== 'completed'" @click="handleFinishPlan">结束测试计划</vort-button>
                        <Dropdown trigger="click" placement="bottomRight">
                            <a class="text-gray-400 hover:text-gray-600 cursor-pointer inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-gray-50">
                                <Ellipsis :size="16" />
                            </a>
                            <template #overlay>
                                <DropdownMenuItem @click="handleEditPlan">编辑</DropdownMenuItem>
                            </template>
                        </Dropdown>
                    </div>
                </div>

                <div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-gray-500">
                    <div class="flex items-center gap-1.5">
                        <span class="text-gray-400">状态:</span>
                        <vort-tag :color="statusColorMap[plan.status] || 'default'">
                            {{ statusLabels[plan.status] || plan.status }}
                        </vort-tag>
                    </div>
                    <div v-if="plan.owner_name" class="flex items-center gap-1.5">
                        <span class="text-gray-400">负责人:</span>
                        <span
                            class="w-5 h-5 rounded-full text-white text-[10px] flex items-center justify-center shrink-0 overflow-hidden"
                            :style="{ backgroundColor: getAvatarBg(plan.owner_name) }"
                        >
                            <img
                                v-if="getMemberAvatarUrl(plan.owner_name)"
                                :src="getMemberAvatarUrl(plan.owner_name)"
                                class="w-full h-full object-cover"
                            >
                            <template v-else>{{ getAvatarLabel(plan.owner_name) }}</template>
                        </span>
                        <span>{{ plan.owner_name }}</span>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-gray-400">已测:</span>
                        <span>{{ plan.executed_cases || 0 }} / {{ plan.total_cases || 0 }}</span>
                    </div>
                    <div class="flex items-center gap-1.5 min-w-[200px]">
                        <span class="text-gray-400">最新结果分布:</span>
                        <vort-tooltip>
                            <div class="flex items-center gap-2 cursor-default">
                                <div class="h-2 bg-gray-100 rounded-full overflow-hidden flex w-[160px]">
                                    <div class="h-full bg-green-500" :style="{ width: resultBarStyle.passed }" />
                                    <div class="h-full bg-red-500" :style="{ width: resultBarStyle.failed }" />
                                    <div class="h-full bg-orange-400" :style="{ width: resultBarStyle.blocked }" />
                                </div>
                                <span class="text-xs text-gray-400">{{ resultPercent }}</span>
                            </div>
                            <template #title>
                                <div class="space-y-1.5 text-sm whitespace-nowrap">
                                    <div v-for="item in resultDistDetail" :key="item.label" class="flex items-center gap-2">
                                        <component v-if="item.icon" :is="item.icon" :size="14" :class="item.color" />
                                        <span v-else class="w-3.5 h-3.5 rounded-full inline-flex items-center justify-center shrink-0">
                                            <span class="w-2 h-2 rounded-full bg-gray-300 inline-block" />
                                        </span>
                                        <span>{{ item.label }}: {{ item.count }} ({{ item.pct }})</span>
                                    </div>
                                </div>
                            </template>
                        </vort-tooltip>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-gray-400">关联迭代:</span>
                        <Dropdown v-model:open="iterLinkOpen" trigger="click">
                            <span class="text-blue-600 cursor-pointer hover:underline" v-if="plan.iteration_name">{{ plan.iteration_name }}</span>
                            <span v-else class="text-gray-500 cursor-pointer hover:text-blue-600">点击关联</span>
                            <template #overlay>
                                <div class="p-2 w-[240px]">
                                    <vort-input-search
                                        v-model="iterLinkSearch"
                                        placeholder="搜索..."
                                        allow-clear
                                        size="small"
                                        class="mb-2"
                                    />
                                    <div class="max-h-[240px] overflow-y-auto">
                                        <div
                                            class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 font-medium text-gray-700"
                                            @click="handleLinkIteration(null)"
                                        >
                                            无关联迭代
                                        </div>
                                        <div
                                            v-for="opt in filteredIterations"
                                            :key="opt.id"
                                            class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 flex items-center justify-between"
                                            :class="plan.iteration_id === opt.id ? 'bg-blue-50 text-blue-600' : 'text-gray-700'"
                                            @click="handleLinkIteration(opt.id)"
                                        >
                                            <span>{{ opt.name }}</span>
                                            <vort-tag v-if="opt.status" size="small" :color="opt.status === 'active' ? 'processing' : 'default'">
                                                {{ iterStatusLabels[opt.status] || opt.status }}
                                            </vort-tag>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </Dropdown>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-gray-400">关联版本:</span>
                        <Dropdown v-model:open="verLinkOpen" trigger="click">
                            <span class="text-blue-600 cursor-pointer hover:underline" v-if="plan.version_name">{{ plan.version_name }}</span>
                            <span v-else class="text-gray-500 cursor-pointer hover:text-blue-600">点击关联</span>
                            <template #overlay>
                                <div class="p-2 w-[240px]">
                                    <vort-input-search
                                        v-model="verLinkSearch"
                                        placeholder="搜索..."
                                        allow-clear
                                        size="small"
                                        class="mb-2"
                                    />
                                    <div class="max-h-[240px] overflow-y-auto">
                                        <div
                                            class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 font-medium text-gray-700"
                                            @click="handleLinkVersion(null)"
                                        >
                                            无关联版本
                                        </div>
                                        <div
                                            v-for="opt in filteredVersions"
                                            :key="opt.id"
                                            class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 flex items-center justify-between"
                                            :class="plan.version_id === opt.id ? 'bg-blue-50 text-blue-600' : 'text-gray-700'"
                                            @click="handleLinkVersion(opt.id)"
                                        >
                                            <span>{{ opt.name }}</span>
                                            <vort-tag v-if="opt.stage" size="small">
                                                {{ verStageLabels[opt.stage] || opt.stage }}
                                            </vort-tag>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </Dropdown>
                    </div>
                </div>

                <div v-if="plan.start_date" class="mt-2 text-sm text-gray-400">
                    计划时间: {{ plan.start_date }} ~ {{ plan.end_date || "" }}
                </div>
            </vort-spin>
        </div>

        <!-- Tabs -->
        <div class="bg-white rounded-xl">
            <vort-tabs v-model:activeKey="activeTab" class="px-6 pt-2">
                <vort-tab-pane tab-key="cases" tab="执行用例" />
                <vort-tab-pane tab-key="report" tab="测试报告" />
            </vort-tabs>

            <!-- Cases Tab Content -->
            <div v-if="activeTab === 'cases'" class="flex min-h-[500px]">
                <!-- Left: Module tree -->
                <div class="w-[220px] border-r border-gray-100 p-4 shrink-0 overflow-y-auto">
                    <div class="flex items-center justify-between mb-3">
                        <span class="text-sm font-medium text-gray-700">功能模块</span>
                        <Search
                            :size="14"
                            class="text-gray-400 cursor-pointer hover:text-gray-600"
                            @click="showModuleSearch = !showModuleSearch"
                        />
                    </div>

                    <div v-if="showModuleSearch" class="mb-2">
                        <vort-input-search
                            v-model="moduleSearch"
                            placeholder="搜索模块"
                            allow-clear
                            size="small"
                        />
                    </div>

                    <!-- All cases -->
                    <div
                        class="flex items-center gap-1.5 px-2 py-1.5 rounded cursor-pointer text-sm mb-1"
                        :class="selectedModuleId === '' ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                        @click="selectModule('')"
                    >
                        <FolderOpen :size="14" />
                        <span>全部用例</span>
                    </div>

                    <!-- Tree nodes -->
                    <div
                        v-for="node in flatNodes"
                        :key="node.id"
                        class="flex items-center gap-1 px-2 py-1.5 rounded cursor-pointer text-sm"
                        :class="selectedModuleId === node.id ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                        :style="{ paddingLeft: `${8 + node.depth * 16}px` }"
                        @click="selectModule(node.id)"
                    >
                        <span
                            v-if="node.hasChildren"
                            class="shrink-0 cursor-pointer"
                            @click.stop="toggleModuleExpand(node.id)"
                        >
                            <ChevronDown v-if="node.expanded" :size="12" />
                            <ChevronRight v-else :size="12" />
                        </span>
                        <span v-else class="w-3 shrink-0" />
                        <component :is="node.hasChildren && node.expanded ? FolderOpen : Folder" :size="14" class="shrink-0" />
                        <span class="truncate">{{ node.name }}</span>
                    </div>
                </div>

                <!-- Right: Cases table -->
                <div class="flex-1 p-4 overflow-x-auto">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-3">
                            <vort-input-search
                                v-model="caseKeyword"
                                placeholder="搜索用例"
                                allow-clear
                                size="small"
                                class="w-[200px]"
                                @search="loadCases"
                                @keyup.enter="loadCases"
                            />
                            <span class="text-sm text-gray-400">共 {{ casesTotal }} 项</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <vort-button variant="primary" size="small" @click="addCasesDialogOpen = true">
                                <Plus :size="14" class="mr-1" /> 添加用例
                            </vort-button>
                        </div>
                    </div>

                    <vort-table :data-source="cases" :loading="casesLoading" :pagination="false" row-key="plan_case_id">
                        <vort-table-column label="编号" :width="80">
                            <template #default="{ row }">
                                <span class="text-xs text-gray-400 font-mono">{{ row.test_case_id?.slice(0, 5)?.toUpperCase() }}</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="标题" :min-width="180">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-800">{{ row.title }}</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="类型" :width="100">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-500">{{ caseTypeLabels[row.case_type] || row.case_type }}</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="优先级" :width="70">
                            <template #default="{ row }">
                                <vort-tag :color="priorityColors[row.priority] || 'default'" size="small">
                                    {{ priorityLabels[row.priority] || `P${row.priority}` }}
                                </vort-tag>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="负责人" :width="100">
                            <template #default="{ row }">
                                <div v-if="row.maintainer_name" class="flex items-center gap-1.5">
                                    <span
                                        class="w-5 h-5 rounded-full text-white text-[10px] flex items-center justify-center shrink-0 overflow-hidden"
                                        :style="{ backgroundColor: getAvatarBg(row.maintainer_name) }"
                                    >
                                        <img
                                            v-if="getMemberAvatarUrl(row.maintainer_name)"
                                            :src="getMemberAvatarUrl(row.maintainer_name)"
                                            class="w-full h-full object-cover"
                                        >
                                        <template v-else>{{ getAvatarLabel(row.maintainer_name) }}</template>
                                    </span>
                                    <span class="text-sm text-gray-600 truncate">{{ row.maintainer_name }}</span>
                                </div>
                                <span v-else class="text-sm text-gray-400">无</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="执行结果分布" :width="140">
                            <template #default="{ row }">
                                <vort-tooltip v-if="row.execution_count">
                                    <div class="flex items-center gap-1">
                                        <span v-if="row.execution_distribution?.passed" class="exec-badge exec-badge-passed">
                                            {{ row.execution_distribution.passed }}
                                        </span>
                                        <span v-if="row.execution_distribution?.blocked" class="exec-badge exec-badge-blocked">
                                            {{ row.execution_distribution.blocked }}
                                        </span>
                                        <span v-if="row.execution_distribution?.failed" class="exec-badge exec-badge-failed">
                                            {{ row.execution_distribution.failed }}
                                        </span>
                                        <span v-if="row.execution_distribution?.skipped" class="exec-badge exec-badge-skipped">
                                            {{ row.execution_distribution.skipped }}
                                        </span>
                                    </div>
                                    <template #title>
                                        <div class="space-y-1 text-sm whitespace-nowrap">
                                            <div v-if="row.execution_distribution?.passed" class="flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-green-500 inline-block shrink-0" />
                                                <span>通过: {{ row.execution_distribution.passed }}</span>
                                            </div>
                                            <div v-if="row.execution_distribution?.blocked" class="flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-orange-400 inline-block shrink-0" />
                                                <span>受阻: {{ row.execution_distribution.blocked }}</span>
                                            </div>
                                            <div v-if="row.execution_distribution?.failed" class="flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-red-500 inline-block shrink-0" />
                                                <span>失败: {{ row.execution_distribution.failed }}</span>
                                            </div>
                                            <div v-if="row.execution_distribution?.skipped" class="flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-blue-400 inline-block shrink-0" />
                                                <span>跳过: {{ row.execution_distribution.skipped }}</span>
                                            </div>
                                        </div>
                                    </template>
                                </vort-tooltip>
                                <span v-else class="text-sm text-gray-400">0</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="最新执行结果" :width="120">
                            <template #default="{ row }">
                                <template v-if="latestResultDisplay(row)">
                                    <div class="flex items-center gap-1">
                                        <component
                                            :is="latestResultDisplay(row)!.icon"
                                            :size="14"
                                            :class="latestResultDisplay(row)!.color"
                                        />
                                        <span class="text-sm" :class="latestResultDisplay(row)!.color">
                                            {{ latestResultDisplay(row)!.label }}
                                        </span>
                                    </div>
                                </template>
                                <span v-else class="text-sm text-gray-400">未执行</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="新增执行结果" :width="110">
                            <template #default="{ row }">
                                <Dropdown v-model:open="executionDropdownOpen[row.plan_case_id]" trigger="click">
                                    <vort-button size="small" class="!px-2">
                                        <Plus :size="12" />
                                    </vort-button>
                                    <template #overlay>
                                        <DropdownMenuItem
                                            v-for="opt in resultOptions"
                                            :key="opt.value"
                                            @click="handleAddExecution(row.plan_case_id, opt.value)"
                                        >
                                            <component :is="opt.icon" :size="14" :class="opt.color" />
                                            <span>{{ opt.label }}</span>
                                        </DropdownMenuItem>
                                    </template>
                                </Dropdown>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="提缺陷" :width="70" align="center">
                            <template #default="{ row }">
                                <vort-tooltip title="提缺陷">
                                    <a class="inline-flex items-center justify-center w-7 h-7 rounded hover:bg-gray-100 cursor-pointer text-gray-400 hover:text-blue-500 transition-colors" @click="handleOpenFileBug(row)">
                                        <Bug :size="16" />
                                    </a>
                                </vort-tooltip>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="操作" :width="60" fixed="right">
                            <template #default="{ row }">
                                <vort-popconfirm title="确认移除此用例？" @confirm="handleRemoveCase(row.plan_case_id)">
                                    <a class="text-sm text-red-500 cursor-pointer">移除</a>
                                </vort-popconfirm>
                            </template>
                        </vort-table-column>
                    </vort-table>
                </div>
            </div>

            <!-- Report Tab Content (placeholder) -->
            <div v-if="activeTab === 'report'" class="p-8 text-center text-gray-400">
                <p class="text-sm">测试报告功能即将推出</p>
            </div>
        </div>

        <!-- Edit Dialog -->
        <TestPlanEditDialog
            v-model:open="editDialogOpen"
            :edit-data="editData"
            @saved="loadPlan"
        />

        <!-- Add Cases Dialog -->
        <TestPlanAddCasesDialog
            v-model:open="addCasesDialogOpen"
            :plan-id="planId"
            :project-id="plan.project_id || ''"
            @saved="handleAddCasesSaved"
        />

        <!-- File Bug Drawer -->
        <vort-drawer
            v-model:open="fileBugDrawerOpen"
            title="提缺陷"
            :width="1180"
            :body-style="{ padding: '16px 20px 20px' }"
        >
            <WorkItemCreate
                ref="createWorkItemRef"
                type="缺陷"
                title="提缺陷"
                use-api
                :project-id="plan.project_id || ''"
                @close="handleCancelFileBug"
            />
            <template #footer>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="handleSubmitFileBug">新建</vort-button>
                    <vort-button @click="handleCancelFileBug">取消</vort-button>
                </div>
            </template>
        </vort-drawer>
    </div>
</template>

<style scoped>
.exec-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 22px;
    height: 22px;
    padding: 0 6px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 4px;
    line-height: 1;
}

.exec-badge-passed {
    color: #16a34a;
    background: #f0fdf4;
}

.exec-badge-blocked {
    color: #ea580c;
    background: #fff7ed;
}

.exec-badge-failed {
    color: #dc2626;
    background: #fef2f2;
}

.exec-badge-skipped {
    color: #2563eb;
    background: #eff6ff;
}
</style>

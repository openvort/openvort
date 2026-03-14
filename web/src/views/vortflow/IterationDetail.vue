<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { onClickOutside } from "@vueuse/core";
import {
    ArrowLeft, Filter, Plus, ListChecks, CheckSquare, Bug,
} from "lucide-vue-next";
import {
    getVortflowIteration, getVortflowIterations,
    getVortflowIterationStories, getVortflowIterationTasks,
    getVortflowStories, getVortflowTasks, getVortflowBugs,
} from "@/api";
import { useVortFlowStore } from "@/stores";

const route = useRoute();
const router = useRouter();
const vortFlowStore = useVortFlowStore();

const iterationId = computed(() => route.params.id as string);

// --- Core state ---
const loading = ref(true);
const iteration = ref<any>({});
const iterations = ref<any[]>([]);
const stories = ref<any[]>([]);
const tasks = ref<any[]>([]);
const bugs = ref<any[]>([]);
const workItemsLoading = ref(false);
const showUnplanned = ref(false);
const unplannedCount = ref(0);

// --- Right-side filters ---
const activeTab = ref("all");
const keyword = ref("");
const statusFilter = ref("");
const assigneeFilter = ref("");

const selectedKeys = ref<(string | number)[]>([]);
const rowSelection = computed(() => ({
    selectedRowKeys: selectedKeys.value,
    onChange: (keys: (string | number)[]) => { selectedKeys.value = keys; },
}));

// --- Sidebar filter popover ---
const sidebarFilterWrapperRef = ref<HTMLElement | null>(null);
const sidebarFilterOpen = ref(false);
const sidebarKeyword = ref("");
const sidebarStatus = ref("");
const sidebarOwner = ref("");
onClickOutside(sidebarFilterWrapperRef, () => { sidebarFilterOpen.value = false; });

// --- Status maps ---
const iterStatusColorMap: Record<string, string> = {
    planning: "default", active: "processing", completed: "green",
};
const iterStatusLabels: Record<string, string> = {
    planning: "待开始", active: "进行中", completed: "已结束",
};

const stateColorMap: Record<string, string> = {
    intake: "default", review: "processing", rejected: "red", pm_refine: "orange",
    design: "cyan", breakdown: "purple", dev_assign: "geekblue", in_progress: "blue",
    testing: "orange", bugfix: "volcano", done: "green",
    todo: "default", closed: "default",
    open: "red", confirmed: "orange", fixing: "processing",
    resolved: "cyan", verified: "green",
};
const stateLabels: Record<string, string> = {
    intake: "意向", review: "评审", rejected: "已驳回", pm_refine: "产品完善",
    design: "UI 设计", breakdown: "拆分估时", dev_assign: "分配开发",
    in_progress: "进行中", testing: "测试中", bugfix: "Bug 修复", done: "已完成",
    todo: "待办", closed: "已关闭",
    open: "打开", confirmed: "已确认", fixing: "修复中",
    resolved: "已解决", verified: "已验证",
};

// --- Unified work item ---
interface WorkItem {
    id: string;
    number: string;
    title: string;
    state: string;
    type: "story" | "task" | "bug";
    tags: string[];
    iterationName: string;
    ownerName: string;
}

const typeIconMap: Record<string, any> = { story: ListChecks, task: CheckSquare, bug: Bug };
const typeColorClass: Record<string, string> = {
    story: "text-blue-500", task: "text-green-500", bug: "text-red-500",
};

const allWorkItems = computed<WorkItem[]>(() => {
    const items: WorkItem[] = [];
    const iterName = showUnplanned.value ? "" : (iteration.value?.name || "");

    for (const s of stories.value) {
        items.push({
            id: s.id, title: s.title || "", state: s.state || "", type: "story",
            tags: Array.isArray(s.tags) ? s.tags : [],
            iterationName: showUnplanned.value ? (s.iteration_name || "-") : iterName,
            ownerName: s.owner_name || s.assignee || "",
            number: s.number || s.code || `S-${(s.id || "").slice(-4)}`,
        });
    }
    for (const t of tasks.value) {
        items.push({
            id: t.id, title: t.title || "", state: t.state || "", type: "task",
            tags: Array.isArray(t.tags) ? t.tags : [],
            iterationName: showUnplanned.value ? (t.iteration_name || "-") : iterName,
            ownerName: t.owner_name || t.assignee || "",
            number: t.number || t.code || `T-${(t.id || "").slice(-4)}`,
        });
    }
    for (const b of bugs.value) {
        items.push({
            id: b.id, title: b.title || "", state: b.state || "", type: "bug",
            tags: Array.isArray(b.tags) ? b.tags : [],
            iterationName: showUnplanned.value ? (b.iteration_name || "-") : iterName,
            ownerName: b.owner_name || b.assignee || "",
            number: b.number || b.code || `B-${(b.id || "").slice(-4)}`,
        });
    }
    return items;
});

const filteredWorkItems = computed(() => {
    let items = allWorkItems.value;
    if (activeTab.value === "story") items = items.filter(i => i.type === "story");
    else if (activeTab.value === "task") items = items.filter(i => i.type === "task");
    else if (activeTab.value === "bug") items = items.filter(i => i.type === "bug");

    const kw = keyword.value.trim().toLowerCase();
    if (kw) items = items.filter(i => i.title.toLowerCase().includes(kw) || i.number.toLowerCase().includes(kw));
    if (statusFilter.value) items = items.filter(i => i.state === statusFilter.value);
    if (assigneeFilter.value) items = items.filter(i => i.ownerName === assigneeFilter.value);
    return items;
});

const storyCount = computed(() => allWorkItems.value.filter(i => i.type === "story").length);
const taskCount = computed(() => allWorkItems.value.filter(i => i.type === "task").length);
const bugCount = computed(() => allWorkItems.value.filter(i => i.type === "bug").length);

const statusOptions = computed(() => {
    const m = new Map<string, string>();
    for (const item of allWorkItems.value) {
        if (item.state && !m.has(item.state)) m.set(item.state, stateLabels[item.state] || item.state);
    }
    return Array.from(m, ([value, label]) => ({ value, label }));
});

const assigneeOptions = computed(() => {
    const names = new Set<string>();
    for (const item of allWorkItems.value) if (item.ownerName) names.add(item.ownerName);
    return Array.from(names);
});

// --- Sidebar computed ---
const sidebarFilterCount = computed(() => {
    let c = 0;
    if (sidebarKeyword.value) c++;
    if (sidebarStatus.value) c++;
    if (sidebarOwner.value) c++;
    return c;
});

const filteredIterations = computed(() => {
    let list = iterations.value;
    const kw = sidebarKeyword.value.trim().toLowerCase();
    if (kw) list = list.filter((i: any) => (i.name || "").toLowerCase().includes(kw));
    if (sidebarStatus.value) list = list.filter((i: any) => i.status === sidebarStatus.value);
    if (sidebarOwner.value) list = list.filter((i: any) => (i.owner_name || "") === sidebarOwner.value);
    return list;
});

const sidebarOwnerOptions = computed(() => {
    const names = new Set<string>();
    for (const iter of iterations.value) if (iter.owner_name) names.add(iter.owner_name);
    return Array.from(names);
});

// --- Helpers ---
const formatDate = (iso: string | null | undefined) => {
    if (!iso) return "-";
    return String(iso).split("T")[0].replace(/-/g, ".");
};

const iterTimeProgress = (iter: any) => {
    if (iter.status === "completed") return 100;
    if (iter.status === "planning") return 0;
    if (!iter.start_date || !iter.end_date) return 0;
    const start = new Date(iter.start_date).getTime();
    const end = new Date(iter.end_date).getTime();
    const now = Date.now();
    if (now <= start) return 0;
    if (now >= end) return 95;
    return Math.round(((now - start) / (end - start)) * 100);
};

const effortPercent = (iter: any) => {
    const actual = iter.actual_hours || 0;
    const estimate = iter.estimate_hours || 0;
    if (!estimate) return 0;
    return Math.min(100, Math.round((actual / estimate) * 100));
};

// --- Data loading ---
const loadIteration = async () => {
    try {
        iteration.value = (await getVortflowIteration(iterationId.value)) || {};
    } catch { iteration.value = {}; }
};

const loadIterations = async () => {
    try {
        const pid = iteration.value?.project_id || vortFlowStore.selectedProjectId || undefined;
        const res = await getVortflowIterations({ project_id: pid, page: 1, page_size: 100 });
        iterations.value = (res as any)?.items || [];
    } catch { iterations.value = []; }
};

const loadWorkItems = async () => {
    workItemsLoading.value = true;
    try {
        const pid = iteration.value?.project_id || vortFlowStore.selectedProjectId || undefined;
        if (showUnplanned.value) {
            const [sRes, tRes, bRes] = await Promise.all([
                getVortflowStories({ project_id: pid, page: 1, page_size: 200 }),
                getVortflowTasks({ project_id: pid, page: 1, page_size: 200 }),
                getVortflowBugs({ project_id: pid, page: 1, page_size: 200 }),
            ]);
            stories.value = (sRes as any)?.items || [];
            tasks.value = (tRes as any)?.items || [];
            bugs.value = (bRes as any)?.items || [];
        } else {
            const [sRes, tRes] = await Promise.all([
                getVortflowIterationStories(iterationId.value),
                getVortflowIterationTasks(iterationId.value),
            ]);
            stories.value = Array.isArray(sRes) ? sRes : ((sRes as any)?.items || []);
            tasks.value = Array.isArray(tRes) ? tRes : ((tRes as any)?.items || []);
            if (pid) {
                const bRes = await getVortflowBugs({ project_id: pid, page: 1, page_size: 100 });
                bugs.value = (bRes as any)?.items || [];
            } else {
                bugs.value = [];
            }
        }
    } catch {
        stories.value = [];
        tasks.value = [];
        bugs.value = [];
    } finally {
        workItemsLoading.value = false;
    }
};

const loadUnplannedCount = async () => {
    try {
        const pid = iteration.value?.project_id || vortFlowStore.selectedProjectId;
        if (!pid) { unplannedCount.value = 0; return; }
        const [sRes, tRes] = await Promise.all([
            getVortflowStories({ project_id: pid, page: 1, page_size: 1 }),
            getVortflowTasks({ project_id: pid, page: 1, page_size: 1 }),
        ]);
        unplannedCount.value = ((sRes as any)?.total || 0) + ((tRes as any)?.total || 0);
    } catch { unplannedCount.value = 0; }
};

const loadAll = async () => {
    loading.value = true;
    try {
        await loadIteration();
        await Promise.all([loadIterations(), loadWorkItems(), loadUnplannedCount()]);
    } finally { loading.value = false; }
};

// --- Handlers ---
const goBack = () => router.push("/vortflow/iterations");

const handleIterationClick = (id: string) => {
    showUnplanned.value = false;
    router.push(`/vortflow/iterations/${id}`);
};

const handleUnplannedClick = () => {
    showUnplanned.value = true;
    loadWorkItems();
};

const handleNewIteration = () => router.push("/vortflow/iterations");

const resetSidebarFilter = () => {
    sidebarKeyword.value = "";
    sidebarStatus.value = "";
    sidebarOwner.value = "";
};

// --- Lifecycle ---
watch(iterationId, () => { if (iterationId.value) loadAll(); });
watch([activeTab, iterationId], () => { selectedKeys.value = []; });

onMounted(() => loadAll());
</script>

<template>
    <div>
        <vort-spin :spinning="loading">
            <div class="space-y-4">
                <!-- Header -->
                <div class="bg-white rounded-xl px-6 py-4">
                    <div class="flex items-center gap-3">
                        <a class="text-gray-400 hover:text-gray-600 cursor-pointer" @click="goBack">
                            <ArrowLeft :size="18" />
                        </a>
                        <h3 class="text-lg font-medium text-gray-800">
                            {{ showUnplanned ? '未规划工作项' : (iteration.name || '迭代详情') }}
                        </h3>
                        <vort-tag
                            v-if="!showUnplanned && iteration.status"
                            :color="iterStatusColorMap[iteration.status] || 'default'"
                        >
                            {{ iterStatusLabels[iteration.status] || iteration.status }}
                        </vort-tag>
                    </div>
                </div>

                <!-- Body: sidebar + main -->
                <div class="flex gap-4 items-start">
                    <!-- Left Sidebar -->
                    <div class="w-[260px] bg-white rounded-xl flex-shrink-0">
                        <!-- Sidebar header -->
                        <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                            <vort-button size="small" @click="handleNewIteration">
                                <Plus :size="12" class="mr-1" /> 新建迭代
                            </vort-button>
                            <div ref="sidebarFilterWrapperRef" class="relative">
                                <vort-button size="small" @click="sidebarFilterOpen = !sidebarFilterOpen">
                                    <Filter :size="12" class="mr-1" /> 筛选 {{ sidebarFilterCount }}
                                </vort-button>
                                <!-- Filter popover -->
                                <div
                                    v-if="sidebarFilterOpen"
                                    class="absolute right-0 top-full mt-2 w-[280px] bg-white rounded-lg shadow-lg border border-gray-200 z-50 p-4"
                                >
                                    <div class="space-y-3">
                                        <div>
                                            <span class="text-xs text-gray-500 block mb-1">搜索迭代</span>
                                            <vort-input v-model="sidebarKeyword" placeholder="迭代名称" allow-clear size="small" />
                                        </div>
                                        <div>
                                            <span class="text-xs text-gray-500 block mb-1">负责人</span>
                                            <vort-select v-model="sidebarOwner" placeholder="全部" allow-clear size="small" class="w-full">
                                                <vort-select-option v-for="n in sidebarOwnerOptions" :key="n" :value="n">{{ n }}</vort-select-option>
                                            </vort-select>
                                        </div>
                                        <div>
                                            <span class="text-xs text-gray-500 block mb-1">迭代状态</span>
                                            <vort-select v-model="sidebarStatus" placeholder="全部" allow-clear size="small" class="w-full">
                                                <vort-select-option value="planning">待开始</vort-select-option>
                                                <vort-select-option value="active">进行中</vort-select-option>
                                                <vort-select-option value="completed">已结束</vort-select-option>
                                            </vort-select>
                                        </div>
                                    </div>
                                    <div class="flex justify-end gap-2 mt-4 pt-3 border-t border-gray-100">
                                        <vort-button size="small" @click="resetSidebarFilter">重置</vort-button>
                                        <vort-button size="small" @click="sidebarFilterOpen = false">取消</vort-button>
                                        <vort-button size="small" variant="primary" @click="sidebarFilterOpen = false">筛选</vort-button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Scrollable iteration list -->
                        <div class="max-h-[calc(100vh-280px)] overflow-y-auto p-3 space-y-2">
                            <!-- Unplanned work items card -->
                            <div
                                class="p-3 rounded-lg cursor-pointer transition-colors border-l-2"
                                :class="showUnplanned ? 'bg-blue-50 border-blue-500' : 'border-transparent hover:bg-gray-50'"
                                @click="handleUnplannedClick"
                            >
                                <div class="flex items-center justify-between">
                                    <span class="text-sm text-gray-700">未规划工作项</span>
                                    <span class="text-sm font-medium text-gray-900">{{ unplannedCount }}</span>
                                </div>
                            </div>

                            <!-- Iteration cards -->
                            <div
                                v-for="iter in filteredIterations"
                                :key="iter.id"
                                class="p-3 rounded-lg cursor-pointer transition-colors border-l-2"
                                :class="!showUnplanned && iter.id === iterationId
                                    ? 'bg-blue-50 border-blue-500'
                                    : 'border-transparent hover:bg-gray-50'"
                                @click="handleIterationClick(iter.id)"
                            >
                                <div class="text-sm font-medium text-gray-800 truncate">{{ iter.name }}</div>
                                <div class="flex items-center gap-2 mt-1">
                                    <span class="iter-status-badge" :class="'iter-status-' + iter.status">
                                        {{ iterStatusLabels[iter.status] || iter.status }}
                                    </span>
                                    <span class="text-[11px] text-gray-400">
                                        {{ formatDate(iter.start_date) }} - {{ formatDate(iter.end_date) }}
                                    </span>
                                </div>
                                <div class="mt-2 space-y-1.5">
                                    <div>
                                        <span class="text-[10px] text-gray-400">工作项进度</span>
                                        <div class="h-1 bg-gray-100 rounded-full overflow-hidden mt-0.5">
                                            <div
                                                class="h-full bg-blue-400 rounded-full transition-all"
                                                :style="{ width: `${iterTimeProgress(iter)}%` }"
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <span class="text-[10px] text-gray-400">工时规模</span>
                                        <div class="h-1 bg-gray-100 rounded-full overflow-hidden mt-0.5">
                                            <div
                                                class="h-full bg-green-400 rounded-full transition-all"
                                                :style="{ width: `${effortPercent(iter)}%` }"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div v-if="filteredIterations.length === 0" class="text-center py-6 text-sm text-gray-400">
                                暂无迭代
                            </div>
                        </div>
                    </div>

                    <!-- Right Main Content -->
                    <div class="flex-1 min-w-0 bg-white rounded-xl">
                        <!-- Unplanned items alert -->
                        <div v-if="unplannedCount > 0 && !showUnplanned" class="px-6 pt-4">
                            <div class="flex items-center gap-2 px-4 py-2.5 bg-blue-50 rounded-lg">
                                <span class="text-sm text-blue-700">
                                    有
                                    <a class="text-blue-600 font-medium cursor-pointer underline" @click="handleUnplannedClick">
                                        {{ unplannedCount }} 个未规划工作项
                                    </a>
                                    未分配到迭代
                                </span>
                            </div>
                        </div>

                        <!-- Tabs -->
                        <div class="px-6 pt-4">
                            <VortTabs v-model:activeKey="activeTab" :hide-content="true">
                                <VortTabPane tab-key="all" :tab="`全部 ${allWorkItems.length}`" />
                                <VortTabPane tab-key="story" :tab="`需求 ${storyCount}`" />
                                <VortTabPane tab-key="task" :tab="`任务 ${taskCount}`" />
                                <VortTabPane tab-key="bug" :tab="`缺陷 ${bugCount}`" />
                            </VortTabs>
                        </div>

                        <!-- Filter bar -->
                        <div class="px-6 py-3 flex items-center gap-3 border-b border-gray-100">
                            <span class="text-sm text-gray-500 whitespace-nowrap">共 {{ filteredWorkItems.length }} 项</span>
                            <vort-input-search
                                v-model="keyword"
                                placeholder="搜索工作项..."
                                allow-clear
                                size="small"
                                class="w-[180px]"
                            />
                            <vort-select v-model="assigneeFilter" placeholder="负责人" allow-clear size="small" class="w-[120px]">
                                <vort-select-option v-for="n in assigneeOptions" :key="n" :value="n">{{ n }}</vort-select-option>
                            </vort-select>
                            <vort-select v-model="statusFilter" placeholder="状态" allow-clear size="small" class="w-[120px]">
                                <vort-select-option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">
                                    {{ opt.label }}
                                </vort-select-option>
                            </vort-select>
                        </div>

                        <!-- Work items table -->
                        <div class="px-6 py-4">
                            <vort-table
                                :data-source="filteredWorkItems"
                                :loading="workItemsLoading"
                                :pagination="false"
                                :row-selection="rowSelection"
                                row-key="id"
                                size="small"
                            >
                                <vort-table-column label="编号" :width="120">
                                    <template #default="{ row }">
                                        <div class="flex items-center gap-1.5">
                                            <component :is="typeIconMap[row.type]" :size="14" :class="typeColorClass[row.type]" />
                                            <span class="text-sm text-gray-600 font-mono">{{ row.number }}</span>
                                        </div>
                                    </template>
                                </vort-table-column>
                                <vort-table-column label="标题" :min-width="200">
                                    <template #default="{ row }">
                                        <span class="text-sm text-gray-800">{{ row.title }}</span>
                                    </template>
                                </vort-table-column>
                                <vort-table-column label="状态" :width="100">
                                    <template #default="{ row }">
                                        <vort-tag :color="stateColorMap[row.state] || 'default'" size="small">
                                            {{ stateLabels[row.state] || row.state || '-' }}
                                        </vort-tag>
                                    </template>
                                </vort-table-column>
                                <vort-table-column label="标签" :width="160">
                                    <template #default="{ row }">
                                        <div class="flex items-center gap-1 flex-wrap">
                                            <vort-tag v-for="tag in (row.tags || []).slice(0, 2)" :key="tag" size="small">
                                                {{ tag }}
                                            </vort-tag>
                                            <span v-if="(row.tags || []).length > 2" class="text-xs text-gray-400">
                                                +{{ row.tags.length - 2 }}
                                            </span>
                                            <span v-if="!(row.tags || []).length" class="text-xs text-gray-400">-</span>
                                        </div>
                                    </template>
                                </vort-table-column>
                                <vort-table-column label="迭代" :width="140">
                                    <template #default="{ row }">
                                        <span class="text-sm text-gray-500 truncate block">{{ row.iterationName || '-' }}</span>
                                    </template>
                                </vort-table-column>
                            </vort-table>
                        </div>
                    </div>
                </div>
            </div>
        </vort-spin>
    </div>
</template>

<style scoped>
.iter-status-badge {
    display: inline-flex;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
    line-height: 18px;
}

.iter-status-planning {
    background: #f3f4f6;
    color: #6b7280;
}

.iter-status-active {
    background: #dbeafe;
    color: #2563eb;
}

.iter-status-completed {
    background: #dcfce7;
    color: #16a34a;
}
</style>

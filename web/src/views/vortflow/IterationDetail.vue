<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Filter, Plus, LayoutList, Ellipsis, Play, CheckCircle, Pencil, Trash2 } from "lucide-vue-next";
import { message } from "@/components/vort";
import {
    getVortflowIteration, getVortflowIterations,
    getVortflowStories, getVortflowTasks, getVortflowBugs,
    updateVortflowIteration, deleteVortflowIteration,
} from "@/api";
import { useVortFlowStore } from "@/stores";
import WorkItemTable from "@/views/vortflow/WorkItemTable.vue";
import IterationEditDialog from "@/views/vortflow/components/IterationEditDialog.vue";

const route = useRoute();
const router = useRouter();
const vortFlowStore = useVortFlowStore();

// Local selected iteration ID, initialized from route param
const selectedIterationId = ref(route.params.id as string);
const iterationId = computed(() => selectedIterationId.value);

const loading = ref(true);
const iteration = ref<any>({});
const iterations = ref<any[]>([]);

type TabType = "需求" | "任务" | "缺陷";
const activeTab = ref<TabType>("需求");

const tabConfig = computed(() => {
    const map: Record<TabType, { pageTitle: string; createBtn: string; createDrawer: string; detailDrawer: string }> = {
        "需求": { pageTitle: "需求列表", createBtn: "+ 新建需求", createDrawer: "新建需求", detailDrawer: "需求详情" },
        "任务": { pageTitle: "任务列表", createBtn: "+ 新建任务", createDrawer: "新建任务", detailDrawer: "任务详情" },
        "缺陷": { pageTitle: "缺陷跟踪", createBtn: "+ 新建缺陷", createDrawer: "新建缺陷", detailDrawer: "缺陷详情" },
    };
    return map[activeTab.value];
});

const projectId = computed(() => iteration.value?.project_id || vortFlowStore.selectedProjectId || "");
const projectName = computed(() =>
    vortFlowStore.projects.find(p => p.id === projectId.value)?.name || ""
);

// Sidebar: "unplanned" vs normal iteration view
const activeView = ref<"unplanned" | "iteration">("iteration");

const isUnplannedView = computed(() => activeView.value === "unplanned");

const effectiveIterationId = computed(() => {
    if (isUnplannedView.value) return "__unplanned__";
    return iterationId.value;
});

// Sidebar filter
const sidebarFilterOpen = ref(false);
const sidebarFilterRef = ref<HTMLElement | null>(null);
const sidebarKeyword = ref("");
const sidebarStatus = ref("");
const sidebarOwner = ref("");

const handleFilterClickOutside = (e: MouseEvent) => {
    if (!sidebarFilterOpen.value) return;
    const target = e.target as HTMLElement;
    if (sidebarFilterRef.value?.contains(target)) return;
    // Ignore clicks on teleported select dropdowns
    if (target.closest(".vort-select-dropdown")) return;
    sidebarFilterOpen.value = false;
};

onMounted(() => document.addEventListener("click", handleFilterClickOutside));
onUnmounted(() => document.removeEventListener("click", handleFilterClickOutside));

// Iteration card action menu
const iterMenuOpen = reactive<Record<string, boolean>>({});

const iterStatusLabels: Record<string, string> = {
    planning: "待开始", active: "进行中", completed: "已结束",
};

const formatDate = (iso: string | null | undefined) => {
    if (!iso) return "-";
    return String(iso).split("T")[0].replace(/-/g, ".");
};

const workItemProgress = (iter: any) => {
    const total = iter.work_item_total || 0;
    const done = iter.work_item_done || 0;
    if (!total) return 0;
    return Math.round((done / total) * 100);
};

const effortPercent = (iter: any) => {
    const actual = iter.actual_hours || 0;
    const estimate = iter.estimate_hours || 0;
    if (!estimate) return 0;
    return Math.min(100, Math.round((actual / estimate) * 100));
};

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

const resetSidebarFilter = () => {
    sidebarKeyword.value = "";
    sidebarStatus.value = "";
    sidebarOwner.value = "";
};

// Unplanned count
const unplannedCount = ref(0);
const loadUnplannedCount = async (pid?: string) => {
    const resolvedPid = pid || projectId.value;
    if (!resolvedPid) return;
    try {
        const [stories, tasks, bugs] = await Promise.all([
            getVortflowStories({ project_id: resolvedPid, iteration_id: "__unplanned__", parent_id: "root", page: 1, page_size: 1 }),
            getVortflowTasks({ project_id: resolvedPid, iteration_id: "__unplanned__", parent_id: "root", page: 1, page_size: 1 }),
            getVortflowBugs({ project_id: resolvedPid, iteration_id: "__unplanned__", page: 1, page_size: 1 }),
        ]);
        unplannedCount.value =
            ((stories as any)?.total || 0) +
            ((tasks as any)?.total || 0) +
            ((bugs as any)?.total || 0);
    } catch { unplannedCount.value = 0; }
};

// Data loading
const loadIteration = async () => {
    try {
        iteration.value = (await getVortflowIteration(iterationId.value)) || {};
    } catch { iteration.value = {}; }
};

const loadIterations = async () => {
    try {
        const pid = iteration.value?.project_id || vortFlowStore.selectedProjectId || undefined;
        const res = await getVortflowIterations({ project_id: pid, page: 1, page_size: 200 });
        iterations.value = (res as any)?.items || [];
    } catch { iterations.value = []; }
};

const loadAll = async () => {
    loading.value = true;
    try {
        await loadIteration();
        await Promise.all([loadIterations(), loadUnplannedCount()]);
    } finally { loading.value = false; }
};

const handleIterationClick = (id: string) => {
    if (id === selectedIterationId.value && activeView.value === "iteration") return;
    activeView.value = "iteration";
    selectedIterationId.value = id;
    iteration.value = iterations.value.find((i: any) => i.id === id) || iteration.value;
    window.history.replaceState({}, "", `/vortflow/iterations/${id}`);
};

const handleUnplannedClick = () => {
    activeView.value = "unplanned";
};

const handleNewIteration = () => {
    editDialogMode.value = "add";
    editDialogIteration.value = { project_id: projectId.value };
    editDialogOpen.value = true;
};

// Edit dialog
const editDialogOpen = ref(false);
const editDialogMode = ref<"add" | "edit">("edit");
const editDialogIteration = ref<any>({});

const handleEditIteration = (iter: any) => {
    editDialogMode.value = "edit";
    editDialogIteration.value = { ...iter };
    editDialogOpen.value = true;
};

const handleEditDialogSaved = () => {
    loadAll();
};

const handleChangeIterationStatus = async (iter: any, status: string) => {
    const label = status === "active" ? "已开始" : "已结束";
    try {
        await updateVortflowIteration(iter.id, { status });
        message.success(`迭代${label}`);
        await loadIterations();
    } catch { message.error("操作失败"); }
};

const handleDeleteIteration = async (iter: any) => {
    try {
        await deleteVortflowIteration(iter.id);
        message.success("迭代已删除");
        await loadIterations();
        if (iter.id === selectedIterationId.value) {
            const first = iterations.value[0];
            if (first) {
                handleIterationClick(first.id);
            } else {
                router.push("/vortflow/iterations");
            }
        }
    } catch { message.error("删除失败"); }
};

watch(() => vortFlowStore.selectedProjectId, async (newPid, oldPid) => {
    if (!newPid || newPid === oldPid) return;
    try {
        const res = await getVortflowIterations({ project_id: newPid, page: 1, page_size: 200 });
        iterations.value = (res as any)?.items || [];
    } catch { iterations.value = []; }
    loadUnplannedCount(newPid);
    const first = iterations.value[0];
    if (first) {
        handleIterationClick(first.id);
    } else {
        activeView.value = "unplanned";
    }
});

onMounted(() => loadAll());
</script>

<template>
    <div>
        <vort-spin :spinning="loading">
            <div class="flex gap-4 items-start" style="min-height: calc(100vh - 120px)">
                <!-- Left Sidebar -->
                <div class="w-[260px] bg-white rounded-xl flex-shrink-0">
                    <!-- Header: new + filter -->
                    <div class="px-4 pt-4 pb-3">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <button
                                    class="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-blue-600 transition-colors cursor-pointer"
                                    @click="handleNewIteration"
                                >
                                    <Plus :size="14" />
                                    <span>新建迭代</span>
                                </button>
                            </div>
                            <div ref="sidebarFilterRef" class="relative">
                                <button
                                    class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-blue-600 transition-colors cursor-pointer"
                                    @click.stop="sidebarFilterOpen = !sidebarFilterOpen"
                                >
                                    <Filter :size="13" />
                                    <span>筛选</span>
                                    <span v-if="sidebarFilterCount" class="text-blue-500 font-medium">{{ sidebarFilterCount }}</span>
                                </button>
                                <Transition name="vort-popover">
                                    <div
                                        v-if="sidebarFilterOpen"
                                        class="absolute right-0 top-full mt-2 w-[260px] bg-white rounded-lg shadow-lg border border-gray-100 z-50 p-4"
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
                                            <div class="flex justify-end gap-2 pt-3 border-t border-gray-100">
                                                <vort-button size="small" @click="resetSidebarFilter">重置</vort-button>
                                                <vort-button size="small" @click="sidebarFilterOpen = false">确定</vort-button>
                                            </div>
                                        </div>
                                    </div>
                                </Transition>
                            </div>
                        </div>
                    </div>

                    <!-- Iteration list -->
                    <div class="max-h-[calc(100vh-220px)] overflow-y-auto px-3 pb-3 space-y-3">
                        <!-- Unplanned work items -->
                        <div
                            class="flex items-center gap-3 px-4 py-3.5 rounded-lg cursor-pointer transition-colors"
                            :class="isUnplannedView
                                ? 'bg-blue-50 text-blue-700'
                                : 'bg-gray-50 hover:bg-gray-100 text-gray-700'"
                            @click="handleUnplannedClick"
                        >
                            <LayoutList :size="16" class="flex-shrink-0 opacity-60" />
                            <span class="text-sm font-medium flex-1">未规划工作项</span>
                            <span class="text-sm tabular-nums" :class="isUnplannedView ? 'text-blue-500' : 'text-gray-400'">
                                {{ unplannedCount }}
                            </span>
                        </div>

                        <!-- Iteration cards -->
                        <div
                            v-for="iter in filteredIterations"
                            :key="iter.id"
                            class="px-4 py-3.5 rounded-lg cursor-pointer transition-colors border"
                            :class="!isUnplannedView && iter.id === iterationId
                                ? 'bg-[#f5f8ff] border-gray-100'
                                : 'border-gray-100 hover:bg-gray-50 hover:border-gray-200'"
                            @click="handleIterationClick(iter.id)"
                        >
                            <div class="flex items-center gap-2">
                                <div class="text-sm font-medium text-gray-800 truncate flex-1">{{ iter.name }}</div>
                                <span @click.stop>
                                    <vort-popover
                                        v-model:open="iterMenuOpen[iter.id]"
                                        trigger="click"
                                        placement="bottomRight"
                                        :arrow="false"
                                        overlay-class="iter-action-popover"
                                    >
                                        <button class="w-6 h-6 flex items-center justify-center rounded hover:bg-gray-200/60 text-gray-400 hover:text-gray-600 transition-colors">
                                            <Ellipsis :size="16" />
                                        </button>
                                        <template #content>
                                            <div class="w-[140px] -mx-3 -my-2">
                                                <button
                                                    v-if="iter.status === 'planning'"
                                                    class="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                                                    @click="iterMenuOpen[iter.id] = false; handleChangeIterationStatus(iter, 'active')"
                                                >
                                                    <Play :size="15" class="text-gray-400" />
                                                    <span>开始迭代</span>
                                                </button>
                                                <button
                                                    v-if="iter.status === 'active'"
                                                    class="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                                                    @click="iterMenuOpen[iter.id] = false; handleChangeIterationStatus(iter, 'completed')"
                                                >
                                                    <CheckCircle :size="15" class="text-gray-400" />
                                                    <span>结束迭代</span>
                                                </button>
                                                <button
                                                    class="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                                                    @click="iterMenuOpen[iter.id] = false; handleEditIteration(iter)"
                                                >
                                                    <Pencil :size="15" class="text-gray-400" />
                                                    <span>编辑</span>
                                                </button>
                                                <div class="border-t border-gray-100 my-1" />
                                                <button
                                                    class="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-red-500 hover:bg-red-50 transition-colors"
                                                    @click="iterMenuOpen[iter.id] = false; handleDeleteIteration(iter)"
                                                >
                                                    <Trash2 :size="15" />
                                                    <span>删除</span>
                                                </button>
                                            </div>
                                        </template>
                                    </vort-popover>
                                </span>
                            </div>
                            <div class="flex items-center gap-2 mt-1.5">
                                <span class="iter-status-badge" :class="'iter-status-' + iter.status">
                                    {{ iterStatusLabels[iter.status] || iter.status }}
                                </span>
                                <span class="text-[11px] text-gray-400">
                                    {{ formatDate(iter.start_date) }} - {{ formatDate(iter.end_date) }}
                                </span>
                            </div>
                            <div class="mt-2.5 space-y-2">
                                <div class="flex items-center gap-2">
                                    <span class="text-[11px] text-gray-400 w-[68px] shrink-0 text-right">工作项进度：</span>
                                    <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                        <div
                                            class="h-full bg-blue-400 rounded-full transition-all"
                                            :style="{ width: `${workItemProgress(iter)}%` }"
                                        />
                                    </div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <span class="text-[11px] text-gray-400 w-[68px] shrink-0 text-right">工时规模：</span>
                                    <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
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
                <div class="flex-1 min-w-0">
                    <!-- Tab switcher -->
                    <div class="bg-white rounded-xl mb-4 px-6 pt-4 pb-0">
                        <div class="flex items-center gap-6 border-b border-gray-100">
                            <button
                                v-for="tab in (['需求', '任务', '缺陷'] as TabType[])"
                                :key="tab"
                                class="pb-3 text-sm font-medium transition-colors relative"
                                :class="activeTab === tab
                                    ? 'text-blue-600'
                                    : 'text-gray-500 hover:text-gray-700'"
                                @click="activeTab = tab"
                            >
                                {{ tab }}
                                <div
                                    v-if="activeTab === tab"
                                    class="absolute bottom-0 left-0 right-0 h-[2px] bg-blue-600 rounded-full"
                                />
                            </button>
                        </div>
                    </div>

                    <!-- WorkItemTable -->
                    <WorkItemTable
                        :key="`${effectiveIterationId}-${activeTab}`"
                        :type="activeTab"
                        :page-title="tabConfig.pageTitle"
                        :create-button-text="tabConfig.createBtn"
                        :create-drawer-title="tabConfig.createDrawer"
                        :detail-drawer-title="tabConfig.detailDrawer"
                        :project-id="projectId"
                        :iteration-id="effectiveIterationId"
                        use-api
                    />
                </div>
            </div>
        </vort-spin>

        <IterationEditDialog
            v-model:open="editDialogOpen"
            :mode="editDialogMode"
            :iteration="editDialogIteration"
            @saved="handleEditDialogSaved"
        />
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

<style>
.iter-action-popover .vort-popover-inner-content {
    padding: 6px 0 !important;
}
</style>

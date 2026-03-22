<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { z } from "zod";
import { useRouter } from "vue-router";
import dayjs from "dayjs";
import {
    FolderKanban, ListChecks, CheckSquare, Bug, Plus, Settings,
    Trash2, Repeat, ArrowRight, User, Calendar, X,
} from "lucide-vue-next";
import { useDirtyCheck } from "@/hooks";
import { useVortFlowStore } from "@/stores";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import {
    getVortflowStats, getVortflowProjects, createVortflowProject,
    updateVortflowProject, deleteVortflowProject,
    getVortgitRepos,
    getVortflowIterations,
    addVortflowProjectMember,
} from "@/api";

interface ProjectItem {
    id: string;
    name: string;
    code: string;
    color: string;
    description: string;
    product: string;
    iteration: string;
    version: string;
    owner_id: string | null;
    start_date: string | null;
    end_date: string | null;
    created_at: string | null;
    story_count: number;
    task_count: number;
    bug_count: number;
}

interface DashboardStats {
    stories: { total: number; done: number };
    tasks: { total: number; done: number };
    bugs: { total: number; closed: number };
}

interface VortgitRepoItem {
    id: string;
    project_id: string | null;
    name: string;
    full_name: string;
    is_private?: boolean;
}

const router = useRouter();
const vortFlowStore = useVortFlowStore();
const {
    memberOptions, ownerGroups, getMemberNameById, getMemberIdByName,
    getAvatarBg, getAvatarLabel, getMemberAvatarUrl, loadMemberOptions,
} = useWorkItemCommon();
const loading = ref(true);
const stats = ref<DashboardStats>({ stories: { total: 0, done: 0 }, tasks: { total: 0, done: 0 }, bugs: { total: 0, closed: 0 } });
const projects = ref<ProjectItem[]>([]);
const projectRepoMap = ref<Record<string, VortgitRepoItem[]>>({});
const iterations = ref<any[]>([]);

const storyProgress = computed(() => {
    const s = stats.value.stories;
    return s.total ? Math.round((s.done / s.total) * 100) : 0;
});
const taskProgress = computed(() => {
    const t = stats.value.tasks;
    return t.total ? Math.round((t.done / t.total) * 100) : 0;
});
const bugCloseRate = computed(() => {
    const b = stats.value.bugs;
    return b.total ? Math.round((b.closed / b.total) * 100) : 0;
});
const bugRateColor = computed(() => {
    const rate = bugCloseRate.value;
    if (rate >= 80) return { stroke: '#22c55e', text: 'text-green-600', border: 'border-green-500' };
    if (rate >= 50) return { stroke: '#f59e0b', text: 'text-amber-500', border: 'border-amber-500' };
    return { stroke: '#ef4444', text: 'text-red-600', border: 'border-red-500' };
});

const projectRepos = (projectId: string) => projectRepoMap.value[projectId] || [];

// SVG ring progress helper
const ringCircumference = 2 * Math.PI * 18;
const ringDashoffset = (percent: number) => ringCircumference * (1 - percent / 100);

// Iteration status helpers
const iterStatusColorMap: Record<string, string> = {
    planning: "default", active: "processing", completed: "green",
};
const iterStatusLabel = (s: string) => {
    const m: Record<string, string> = { planning: "规划中", active: "进行中", completed: "已完成" };
    return m[s] || s;
};

const activeIterations = computed(() =>
    iterations.value.filter((i: any) => i.status === "active"),
);

const iterProgress = (row: any) => {
    if (!row.work_item_total) return 0;
    return Math.round((row.work_item_done / row.work_item_total) * 100);
};

const daysRemaining = (endDate: string | null | undefined) => {
    if (!endDate) return null;
    const end = dayjs(endDate);
    if (!end.isValid()) return null;
    return end.diff(dayjs(), "day");
};

const formatDate = (iso: string | null | undefined) => {
    if (!iso) return "-";
    return String(iso).split("T")[0];
};

const loadData = async () => {
    loading.value = true;
    try {
        const [statsRes, projectsRes, iterRes] = await Promise.all([
            getVortflowStats(), getVortflowProjects(),
            getVortflowIterations({ page: 1, page_size: 100 }),
        ]);
        if (statsRes) {
            const r = statsRes as any;
            stats.value = {
                stories: r.stories ?? { total: 0, done: 0 },
                tasks: r.tasks ?? { total: 0, done: 0 },
                bugs: r.bugs ?? { total: 0, closed: 0 },
            };
        }
        projects.value = (projectsRes as any)?.items || [];
        vortFlowStore.loadProjects();
        iterations.value = (iterRes as any)?.items || [];

        try {
            const reposRes = await getVortgitRepos({ page: 1, page_size: 100 });
            const repos = ((reposRes as any)?.items || []) as VortgitRepoItem[];
            const grouped: Record<string, VortgitRepoItem[]> = {};
            for (const repo of repos) {
                if (!repo.project_id) continue;
                if (!grouped[repo.project_id]) grouped[repo.project_id] = [];
                grouped[repo.project_id].push(repo);
            }
            projectRepoMap.value = grouped;
        } catch {
            projectRepoMap.value = {};
        }
    } catch { /* silent */ }
    finally { loading.value = false; }
};

// Project drawer
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentProject = ref<Partial<ProjectItem>>({});
const formRef = ref();
const formLoading = ref(false);
const { takeSnapshot, confirmClose } = useDirtyCheck(currentProject);

const PROJECT_COLOR_PRESETS = [
    "#3b82f6", "#ef4444", "#f97316", "#eab308", "#a3e635",
    "#22c55e", "#14b8a6", "#06b6d4", "#6366f1", "#8b5cf6",
    "#a855f7", "#d946ef",
];

const selectedOwnerName = ref("");
const selectedMemberNames = ref<string[]>([]);
const selectedRepoIds = ref<string[]>([]);
const allRepos = ref<VortgitRepoItem[]>([]);

const loadAllRepos = async () => {
    try {
        const res = await getVortgitRepos({ page: 1, page_size: 200 });
        allRepos.value = ((res as any)?.items || []) as VortgitRepoItem[];
    } catch { allRepos.value = []; }
};

const projectValidationSchema = z.object({
    name: z.string().min(1, '项目名称不能为空'),
    code: z.string().optional().or(z.literal('')),
    color: z.string().optional().or(z.literal('')),
    product: z.string().optional().or(z.literal('')),
    start_date: z.string().optional().or(z.literal('')),
    end_date: z.string().optional().or(z.literal('')),
    description: z.string().optional().or(z.literal('')),
});

const resetDrawerExtras = () => {
    selectedOwnerName.value = "";
    selectedMemberNames.value = [];
    selectedRepoIds.value = [];
};

const handleAddProject = async () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增项目";
    currentProject.value = { color: "#3b82f6" };
    resetDrawerExtras();
    drawerVisible.value = true;
    takeSnapshot();
    await Promise.all([loadMemberOptions(), loadAllRepos()]);
};

const handleEditProject = async (p: ProjectItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑项目";
    currentProject.value = {
        ...p,
        start_date: p.start_date ? p.start_date.split("T")[0] : "",
        end_date: p.end_date ? p.end_date.split("T")[0] : "",
    };
    resetDrawerExtras();
    if (p.owner_id) {
        selectedOwnerName.value = getMemberNameById(p.owner_id) || "";
    }
    const linkedRepos = projectRepos(p.id);
    selectedRepoIds.value = linkedRepos.map((r) => r.id);
    drawerVisible.value = true;
    takeSnapshot();
    await Promise.all([loadMemberOptions(), loadAllRepos()]);
};

const handleViewProject = (p: ProjectItem) => {
    vortFlowStore.setProjectId(p.id);
    router.push(`/vortflow/projects/${p.id}`);
};

const handleSaveProject = async () => {
    try { await formRef.value?.validate(); } catch { return; }
    const r = currentProject.value;
    formLoading.value = true;
    try {
        const ownerId = getMemberIdByName(selectedOwnerName.value) || undefined;
        if (drawerMode.value === "add") {
            const memberIds = selectedMemberNames.value
                .map((n) => getMemberIdByName(n))
                .filter(Boolean) as string[];
            await createVortflowProject({
                name: r.name!, code: r.code, color: r.color,
                description: r.description, product: r.product,
                start_date: r.start_date || undefined, end_date: r.end_date || undefined,
                owner_id: ownerId, member_ids: memberIds,
                repo_ids: selectedRepoIds.value.length ? selectedRepoIds.value : undefined,
            });
        } else {
            await updateVortflowProject(r.id!, {
                name: r.name, code: r.code, color: r.color,
                description: r.description, product: r.product,
                start_date: r.start_date || undefined, end_date: r.end_date || undefined,
                owner_id: ownerId,
            });
        }
        drawerVisible.value = false;
        loadData();
    } finally { formLoading.value = false; }
};

const handleDeleteProject = async (p: ProjectItem) => {
    await deleteVortflowProject(p.id);
    loadData();
};

const goToWorkItems = (type: string) => {
    const pathMap: Record<string, string> = { stories: "/vortflow/stories", tasks: "/vortflow/tasks", bugs: "/vortflow/bugs" };
    router.push(pathMap[type] || "/vortflow/stories");
};

const goToIterationDetail = (id: string) => {
    router.push(`/vortflow/iterations?id=${id}`);
};

const goToAllIterations = () => {
    router.push("/vortflow/iterations");
};

onMounted(() => {
    loadData();
    loadMemberOptions();
});

watch(() => vortFlowStore.selectedProjectId, () => {
    loadData();
});
</script>

<template>
    <div class="space-y-4">
        <vort-spin :spinning="loading">
            <div class="space-y-4">
            <!-- Stats -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <!-- Stories -->
                <div class="bg-white rounded-xl p-5 border-l-4 border-blue-500 cursor-pointer hover:shadow-md transition-shadow" @click="goToWorkItems('stories')">
                    <div class="flex items-center gap-4">
                        <div class="relative w-14 h-14 flex-shrink-0">
                            <svg viewBox="0 0 40 40" class="w-full h-full -rotate-90">
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#e5e7eb" stroke-width="3" />
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#3b82f6" stroke-width="3"
                                    stroke-linecap="round"
                                    :stroke-dasharray="ringCircumference"
                                    :stroke-dashoffset="ringDashoffset(storyProgress)"
                                    class="transition-all duration-500"
                                />
                            </svg>
                            <div class="absolute inset-0 flex items-center justify-center">
                                <span class="text-xs font-semibold text-blue-600">{{ storyProgress }}%</span>
                            </div>
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-2">
                                    <ListChecks :size="15" class="text-blue-600" />
                                    <span class="text-sm font-medium text-gray-600">需求</span>
                                </div>
                                <span class="text-2xl font-bold text-gray-800">{{ stats.stories.total }}</span>
                            </div>
                            <div class="flex items-center justify-between mt-1.5 text-xs text-gray-400">
                                <span>已完成 {{ stats.stories.done }}/{{ stats.stories.total }}</span>
                                <ArrowRight :size="12" class="text-gray-300" />
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Tasks -->
                <div class="bg-white rounded-xl p-5 border-l-4 border-green-500 cursor-pointer hover:shadow-md transition-shadow" @click="goToWorkItems('tasks')">
                    <div class="flex items-center gap-4">
                        <div class="relative w-14 h-14 flex-shrink-0">
                            <svg viewBox="0 0 40 40" class="w-full h-full -rotate-90">
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#e5e7eb" stroke-width="3" />
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#22c55e" stroke-width="3"
                                    stroke-linecap="round"
                                    :stroke-dasharray="ringCircumference"
                                    :stroke-dashoffset="ringDashoffset(taskProgress)"
                                    class="transition-all duration-500"
                                />
                            </svg>
                            <div class="absolute inset-0 flex items-center justify-center">
                                <span class="text-xs font-semibold text-green-600">{{ taskProgress }}%</span>
                            </div>
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-2">
                                    <CheckSquare :size="15" class="text-green-600" />
                                    <span class="text-sm font-medium text-gray-600">任务</span>
                                </div>
                                <span class="text-2xl font-bold text-gray-800">{{ stats.tasks.total }}</span>
                            </div>
                            <div class="flex items-center justify-between mt-1.5 text-xs text-gray-400">
                                <span>已完成 {{ stats.tasks.done }}/{{ stats.tasks.total }}</span>
                                <ArrowRight :size="12" class="text-gray-300" />
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Bugs -->
                <div :class="['bg-white rounded-xl p-5 border-l-4 cursor-pointer hover:shadow-md transition-shadow', bugRateColor.border]" @click="goToWorkItems('bugs')">
                    <div class="flex items-center gap-4">
                        <div class="relative w-14 h-14 flex-shrink-0">
                            <svg viewBox="0 0 40 40" class="w-full h-full -rotate-90">
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#e5e7eb" stroke-width="3" />
                                <circle cx="20" cy="20" r="18" fill="none" :stroke="bugRateColor.stroke" stroke-width="3"
                                    stroke-linecap="round"
                                    :stroke-dasharray="ringCircumference"
                                    :stroke-dashoffset="ringDashoffset(bugCloseRate)"
                                    class="transition-all duration-500"
                                />
                            </svg>
                            <div class="absolute inset-0 flex items-center justify-center">
                                <span :class="['text-xs font-semibold', bugRateColor.text]">{{ bugCloseRate }}%</span>
                            </div>
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-2">
                                    <Bug :size="15" :class="bugRateColor.text" />
                                    <span class="text-sm font-medium text-gray-600">缺陷</span>
                                </div>
                                <span class="text-2xl font-bold text-gray-800">{{ stats.bugs.total }}</span>
                            </div>
                            <div class="flex items-center justify-between mt-1.5 text-xs text-gray-400">
                                <span>已关闭 {{ stats.bugs.closed }}/{{ stats.bugs.total }}</span>
                                <ArrowRight :size="12" class="text-gray-300" />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Projects -->
            <div class="bg-white rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-base font-medium text-gray-800">项目</h3>
                    <div class="flex items-center gap-2">
                        <AiAssistButton
                            prompt="我想创建一个新的 VortFlow 项目，请引导我完成设置，包括项目名称、描述、起止时间。"
                        />
                        <vort-button variant="primary" @click="handleAddProject">
                            <Plus :size="14" class="mr-1" /> 新增项目
                        </vort-button>
                    </div>
                </div>
                <div v-if="projects.length === 0" class="text-center py-12 text-gray-400">
                    <FolderKanban :size="48" class="mx-auto mb-3 text-gray-300" />
                    <p>暂无项目，点击上方按钮创建第一个项目</p>
                </div>
                <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div v-for="p in projects" :key="p.id"
                        class="border border-gray-100 rounded-xl p-4 hover:shadow-md hover:-translate-y-0.5 transition-all cursor-pointer group relative"
                        @click="handleViewProject(p)"
                    >
                        <!-- Header -->
                        <div class="flex items-start justify-between mb-2.5">
                            <div class="flex items-center gap-2.5 min-w-0 flex-1">
                                <div class="w-9 h-9 rounded-lg flex items-center justify-center text-white text-sm font-semibold flex-shrink-0 shadow-sm"
                                    :style="{ backgroundColor: p.color || '#3b82f6' }">
                                    {{ (p.code || p.name || '?')[0].toUpperCase() }}
                                </div>
                                <div class="min-w-0">
                                    <h4 class="font-medium text-gray-800 truncate text-sm">{{ p.name }}</h4>
                                    <p class="text-xs text-gray-400 line-clamp-1 mt-0.5">{{ p.description || '暂无描述' }}</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2 flex-shrink-0" @click.stop>
                                <vort-tooltip title="编辑">
                                    <a class="text-gray-400 hover:text-blue-600 cursor-pointer p-0.5" @click="handleEditProject(p)">
                                        <Settings :size="13" />
                                    </a>
                                </vort-tooltip>
                                <vort-popconfirm title="确认删除该项目？" @confirm="handleDeleteProject(p)">
                                    <a class="text-gray-400 hover:text-red-500 cursor-pointer p-0.5">
                                        <Trash2 :size="13" />
                                    </a>
                                </vort-popconfirm>
                            </div>
                        </div>

                        <!-- Owner -->
                        <div v-if="p.owner_id" class="flex items-center gap-1.5 text-xs text-gray-500 mb-2.5">
                            <User :size="11" class="text-gray-400" />
                            <span>{{ getMemberNameById(p.owner_id) || p.owner_id }}</span>
                        </div>

                        <!-- Work item counts -->
                        <div class="flex items-center gap-4 text-xs text-gray-500 mb-3">
                            <span class="flex items-center gap-1" :class="(p.story_count || 0) > 0 ? 'text-blue-600' : ''">
                                <ListChecks :size="12" /> 需求 {{ p.story_count || 0 }}
                            </span>
                            <span class="flex items-center gap-1" :class="(p.task_count || 0) > 0 ? 'text-green-600' : ''">
                                <CheckSquare :size="12" /> 任务 {{ p.task_count || 0 }}
                            </span>
                            <span class="flex items-center gap-1" :class="(p.bug_count || 0) > 0 ? 'text-red-500' : ''">
                                <Bug :size="12" /> 缺陷 {{ p.bug_count || 0 }}
                            </span>
                        </div>

                        <!-- Repos -->
                        <div v-if="projectRepos(p.id).length > 0" class="flex flex-wrap gap-1.5 pt-2.5 border-t border-gray-100">
                            <vort-tag
                                v-for="repo in projectRepos(p.id).slice(0, 3)"
                                :key="repo.id"
                                size="small"
                                color="processing"
                            >
                                {{ repo.name }}
                            </vort-tag>
                            <span v-if="projectRepos(p.id).length > 3" class="text-xs text-gray-400 leading-5">
                                +{{ projectRepos(p.id).length - 3 }}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Active Iterations -->
            <div class="bg-white rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-base font-medium text-gray-800">
                        <Repeat :size="16" class="inline mr-1.5 text-blue-500" />当前迭代
                    </h3>
                    <a class="text-sm text-blue-500 hover:text-blue-700 cursor-pointer flex items-center gap-1" @click="goToAllIterations">
                        查看所有迭代 <ArrowRight :size="14" />
                    </a>
                </div>
                <div v-if="activeIterations.length === 0 && iterations.length === 0" class="text-center py-8 text-gray-400">
                    <Repeat :size="36" class="mx-auto mb-2 text-gray-300" />
                    <p class="text-sm">暂无迭代数据</p>
                </div>
                <template v-else>
                    <vort-table
                        :data-source="activeIterations.length > 0 ? activeIterations : iterations.slice(0, 5)"
                        :pagination="false"
                        size="small"
                    >
                        <vort-table-column label="标题" prop="name" :width="160">
                            <template #default="{ row }">
                                <a class="text-sm text-blue-600 hover:underline cursor-pointer" @click.stop="goToIterationDetail(row.id)">
                                    {{ row.name }}
                                </a>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="状态" :width="90">
                            <template #default="{ row }">
                                <vort-tag :color="iterStatusColorMap[row.status] || 'default'" size="small">
                                    {{ iterStatusLabel(row.status) }}
                                </vort-tag>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="起止时间" :width="200">
                            <template #default="{ row }">
                                <span class="text-xs text-gray-500">
                                    {{ formatDate(row.start_date) }} ~ {{ formatDate(row.end_date) }}
                                </span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="进度" :width="180">
                            <template #default="{ row }">
                                <div v-if="row.work_item_total" class="flex items-center gap-2">
                                    <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                        <div
                                            class="h-full rounded-full transition-all duration-500"
                                            :class="iterProgress(row) >= 100 ? 'bg-green-500' : iterProgress(row) >= 50 ? 'bg-blue-500' : 'bg-orange-400'"
                                            :style="{ width: iterProgress(row) + '%' }"
                                        />
                                    </div>
                                    <span class="text-xs text-gray-500 whitespace-nowrap w-16 text-right">
                                        {{ row.work_item_done }}/{{ row.work_item_total }}
                                    </span>
                                </div>
                                <span v-else class="text-xs text-gray-300">-</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="剩余" :width="80">
                            <template #default="{ row }">
                                <template v-if="daysRemaining(row.end_date) !== null">
                                    <span v-if="daysRemaining(row.end_date)! < 0" class="text-xs text-red-500 font-medium">
                                        逾期 {{ Math.abs(daysRemaining(row.end_date)!) }}天
                                    </span>
                                    <span v-else-if="daysRemaining(row.end_date)! <= 3" class="text-xs text-orange-500 font-medium">
                                        {{ daysRemaining(row.end_date) }}天
                                    </span>
                                    <span v-else class="text-xs text-gray-500">
                                        {{ daysRemaining(row.end_date) }}天
                                    </span>
                                </template>
                                <span v-else class="text-xs text-gray-300">-</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="目标" :min-width="160">
                            <template #default="{ row }">
                                <span class="text-xs text-gray-400 line-clamp-1">{{ row.goal || '-' }}</span>
                            </template>
                        </vort-table-column>
                    </vort-table>
                </template>
            </div>
            </div>
        </vort-spin>

        <!-- Project Drawer -->
        <vort-drawer :open="drawerVisible" :title="drawerTitle" :width="900" @update:open="(val: boolean) => { if (!val) { confirmClose(() => { drawerVisible = false }) } else { drawerVisible = val } }">
            <vort-form ref="formRef" :model="currentProject" :rules="projectValidationSchema" label-width="100px">
                <vort-form-item label="项目名称" name="name" required has-feedback>
                    <vort-input v-model="currentProject.name" placeholder="请输入项目名称" />
                </vort-form-item>
                <vort-form-item label="项目编号" name="code">
                    <vort-input v-model="currentProject.code" placeholder="方便记忆的名称或代号（可选）" />
                </vort-form-item>
                <vort-form-item label="颜色" name="color">
                    <div class="flex items-center gap-2 flex-wrap">
                        <button
                            v-for="c in PROJECT_COLOR_PRESETS" :key="c"
                            type="button"
                            class="w-7 h-7 rounded-md border-2 transition-all flex items-center justify-center"
                            :class="currentProject.color === c ? 'border-gray-700 scale-110' : 'border-transparent hover:scale-105'"
                            :style="{ backgroundColor: c }"
                            @click="currentProject.color = c"
                        >
                            <svg v-if="currentProject.color === c" class="w-4 h-4 text-white" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                            </svg>
                        </button>
                    </div>
                </vort-form-item>
                <vort-form-item label="产品" name="product">
                    <vort-input v-model="currentProject.product" placeholder="产品名称（可选）" />
                </vort-form-item>
                <vort-form-item label="关联仓库">
                    <vort-select
                        v-model="selectedRepoIds"
                        mode="multiple"
                        placeholder="请选择关联仓库"
                        class="w-full"
                        :allow-clear="true"
                        :max-tag-count="3"
                    >
                        <vort-select-option v-for="repo in allRepos" :key="repo.id" :value="repo.id">
                            <div class="flex items-center justify-between w-full">
                                <span class="truncate">{{ repo.full_name || repo.name }}</span>
                                <span class="text-xs text-gray-400 ml-2 flex-shrink-0">{{ repo.is_private ? '私有' : '外部开源' }}</span>
                            </div>
                        </vort-select-option>
                    </vort-select>
                </vort-form-item>
                <vort-form-item label="项目负责人">
                    <WorkItemMemberPicker
                        mode="owner"
                        :owner="selectedOwnerName"
                        :groups="ownerGroups"
                        :get-avatar-bg="getAvatarBg"
                        :get-avatar-label="getAvatarLabel"
                        :get-avatar-url="getMemberAvatarUrl"
                        placeholder="请选择负责人"
                        :bordered="true"
                        :dropdown-width="380"
                        @update:owner="selectedOwnerName = $event"
                    >
                        <template #trigger="{ open: triggerOpen }">
                            <div class="border rounded-lg px-3 py-1.5 cursor-pointer hover:border-blue-400 transition-colors flex items-center gap-2 min-h-[34px]"
                                :class="triggerOpen ? 'border-blue-400' : 'border-gray-200'">
                                <template v-if="selectedOwnerName">
                                    <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs text-white flex-shrink-0"
                                        :style="{ backgroundColor: getAvatarBg(selectedOwnerName) }">
                                        <img v-if="getMemberAvatarUrl(selectedOwnerName)" :src="getMemberAvatarUrl(selectedOwnerName)" class="w-full h-full rounded-full object-cover" />
                                        <template v-else>{{ getAvatarLabel(selectedOwnerName) }}</template>
                                    </div>
                                    <span class="text-sm text-gray-800">{{ selectedOwnerName }}</span>
                                </template>
                                <span v-else class="text-sm text-gray-400">请选择负责人</span>
                            </div>
                        </template>
                    </WorkItemMemberPicker>
                </vort-form-item>
                <vort-form-item v-if="drawerMode === 'add'" label="成员">
                    <WorkItemMemberPicker
                        mode="collaborators"
                        :collaborators="selectedMemberNames"
                        :groups="ownerGroups"
                        :get-avatar-bg="getAvatarBg"
                        :get-avatar-label="getAvatarLabel"
                        :get-avatar-url="getMemberAvatarUrl"
                        placeholder="请选择企业成员，可多选"
                        :bordered="true"
                        :dropdown-width="380"
                        @update:collaborators="selectedMemberNames = $event"
                    >
                        <template #trigger="{ open: triggerOpen }">
                            <div class="border rounded-lg px-3 py-1.5 cursor-pointer hover:border-blue-400 transition-colors flex items-center gap-2 min-h-[34px] flex-wrap"
                                :class="triggerOpen ? 'border-blue-400' : 'border-gray-200'">
                                <template v-if="selectedMemberNames.length">
                                    <span v-for="name in selectedMemberNames" :key="name"
                                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700 border border-blue-200">
                                        <span class="w-4 h-4 rounded-full flex items-center justify-center text-[10px] text-white flex-shrink-0"
                                            :style="{ backgroundColor: getAvatarBg(name) }">
                                            <img v-if="getMemberAvatarUrl(name)" :src="getMemberAvatarUrl(name)" class="w-full h-full rounded-full object-cover" />
                                            <template v-else>{{ getAvatarLabel(name) }}</template>
                                        </span>
                                        {{ name }}
                                        <button type="button" class="ml-0.5 text-blue-400 hover:text-blue-600" @click.stop="selectedMemberNames = selectedMemberNames.filter(n => n !== name)">
                                            <X :size="10" />
                                        </button>
                                    </span>
                                </template>
                                <span v-else class="text-sm text-gray-400">请选择企业成员，可多选</span>
                            </div>
                        </template>
                    </WorkItemMemberPicker>
                </vort-form-item>
                <vort-form-item label="开始日期" name="start_date">
                    <vort-date-picker v-model="currentProject.start_date" value-format="YYYY-MM-DD" placeholder="请选择开始日期" class="w-full" />
                </vort-form-item>
                <vort-form-item label="结束日期" name="end_date">
                    <vort-date-picker v-model="currentProject.end_date" value-format="YYYY-MM-DD" placeholder="请选择结束日期" class="w-full" />
                </vort-form-item>
                <vort-form-item label="描述" name="description">
                    <VortEditor v-model="currentProject.description" placeholder="请输入项目描述" min-height="160px" />
                </vort-form-item>
            </vort-form>
            <div class="flex justify-end gap-3 mt-6">
                <vort-button @click="confirmClose(() => { drawerVisible = false })">取消</vort-button>
                <vort-button variant="primary" :loading="formLoading" @click="handleSaveProject">确定</vort-button>
            </div>
        </vort-drawer>
    </div>
</template>

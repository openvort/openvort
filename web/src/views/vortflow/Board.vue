<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { z } from "zod";
import { useRouter } from "vue-router";
import {
    FolderKanban, ListChecks, CheckSquare, Bug, Plus, Settings,
    Trash2, Repeat, Filter, ArrowRight, User, Calendar,
} from "lucide-vue-next";
import { useDirtyCheck } from "@/hooks";
import { useVortFlowStore } from "@/stores";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import {
    getVortflowStats, getVortflowProjects, createVortflowProject,
    updateVortflowProject, deleteVortflowProject,
    getVortgitRepos,
    getVortflowIterations, getVortflowVersions,
} from "@/api";

interface ProjectItem {
    id: string;
    name: string;
    description: string;
    product: string;
    iteration: string;
    version: string;
    owner_id: string | null;
    start_date: string | null;
    end_date: string | null;
    created_at: string | null;
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
}

const router = useRouter();
const vortFlowStore = useVortFlowStore();
const { getMemberNameById, loadMemberOptions } = useWorkItemCommon();
const loading = ref(true);
const stats = ref<DashboardStats>({ stories: { total: 0, done: 0 }, tasks: { total: 0, done: 0 }, bugs: { total: 0, closed: 0 } });
const projects = ref<ProjectItem[]>([]);
const projectRepoMap = ref<Record<string, VortgitRepoItem[]>>({});
const iterations = ref<any[]>([]);
const versions = ref<any[]>([]);
const selectedIterationId = ref("");
const selectedVersionId = ref("");

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

const formatDate = (iso: string | null | undefined) => {
    if (!iso) return "-";
    return String(iso).split("T")[0];
};

const loadData = async () => {
    loading.value = true;
    try {
        const selectedPid = vortFlowStore.selectedProjectId || undefined;
        const [statsRes, projectsRes, iterRes, verRes] = await Promise.all([
            getVortflowStats(selectedPid), getVortflowProjects(),
            getVortflowIterations({ project_id: selectedPid, page: 1, page_size: 100 }),
            getVortflowVersions({ project_id: selectedPid, page: 1, page_size: 100 }),
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
        versions.value = (verRes as any)?.items || [];

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

const projectValidationSchema = z.object({
    name: z.string().min(1, '项目名称不能为空'),
    product: z.string().optional().or(z.literal('')),
    iteration: z.string().optional().or(z.literal('')),
    version: z.string().optional().or(z.literal('')),
    start_date: z.string().optional().or(z.literal('')),
    end_date: z.string().optional().or(z.literal('')),
    description: z.string().optional().or(z.literal('')),
});

const handleAddProject = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增项目";
    currentProject.value = {};
    drawerVisible.value = true;
    takeSnapshot();
};

const handleEditProject = (p: ProjectItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑项目";
    currentProject.value = {
        ...p,
        start_date: p.start_date ? p.start_date.split("T")[0] : "",
        end_date: p.end_date ? p.end_date.split("T")[0] : "",
    };
    drawerVisible.value = true;
    takeSnapshot();
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
        if (drawerMode.value === "add") {
            await createVortflowProject({
                name: r.name!, description: r.description,
                product: r.product, iteration: r.iteration, version: r.version,
                start_date: r.start_date || undefined, end_date: r.end_date || undefined,
            });
        } else {
            await updateVortflowProject(r.id!, {
                name: r.name, description: r.description,
                product: r.product, iteration: r.iteration, version: r.version,
                start_date: r.start_date || undefined, end_date: r.end_date || undefined,
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
            <!-- Stats with SVG ring -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <!-- Stories -->
                <div class="bg-white rounded-xl p-6">
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
                                    <div class="w-7 h-7 rounded-lg bg-blue-50 flex items-center justify-center">
                                        <ListChecks :size="14" class="text-blue-600" />
                                    </div>
                                    <span class="text-sm text-gray-500">需求</span>
                                </div>
                                <span class="text-2xl font-bold text-gray-800">{{ stats.stories.total }}</span>
                            </div>
                            <div class="flex items-center justify-between mt-2 text-xs text-gray-400">
                                <span>已完成 {{ stats.stories.done }}</span>
                            </div>
                        </div>
                    </div>
                    <div class="mt-3 pt-3 border-t border-gray-100">
                        <a class="text-xs text-blue-500 hover:text-blue-700 cursor-pointer flex items-center gap-1" @click="goToWorkItems('stories')">
                            查看全部需求 <ArrowRight :size="12" />
                        </a>
                    </div>
                </div>

                <!-- Tasks -->
                <div class="bg-white rounded-xl p-6">
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
                                    <div class="w-7 h-7 rounded-lg bg-green-50 flex items-center justify-center">
                                        <CheckSquare :size="14" class="text-green-600" />
                                    </div>
                                    <span class="text-sm text-gray-500">任务</span>
                                </div>
                                <span class="text-2xl font-bold text-gray-800">{{ stats.tasks.total }}</span>
                            </div>
                            <div class="flex items-center justify-between mt-2 text-xs text-gray-400">
                                <span>已完成 {{ stats.tasks.done }}</span>
                            </div>
                        </div>
                    </div>
                    <div class="mt-3 pt-3 border-t border-gray-100">
                        <a class="text-xs text-blue-500 hover:text-blue-700 cursor-pointer flex items-center gap-1" @click="goToWorkItems('tasks')">
                            查看全部任务 <ArrowRight :size="12" />
                        </a>
                    </div>
                </div>

                <!-- Bugs -->
                <div class="bg-white rounded-xl p-6">
                    <div class="flex items-center gap-4">
                        <div class="relative w-14 h-14 flex-shrink-0">
                            <svg viewBox="0 0 40 40" class="w-full h-full -rotate-90">
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#e5e7eb" stroke-width="3" />
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#ef4444" stroke-width="3"
                                    stroke-linecap="round"
                                    :stroke-dasharray="ringCircumference"
                                    :stroke-dashoffset="ringDashoffset(bugCloseRate)"
                                    class="transition-all duration-500"
                                />
                            </svg>
                            <div class="absolute inset-0 flex items-center justify-center">
                                <span class="text-xs font-semibold text-red-600">{{ bugCloseRate }}%</span>
                            </div>
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-2">
                                    <div class="w-7 h-7 rounded-lg bg-red-50 flex items-center justify-center">
                                        <Bug :size="14" class="text-red-600" />
                                    </div>
                                    <span class="text-sm text-gray-500">缺陷</span>
                                </div>
                                <span class="text-2xl font-bold text-gray-800">{{ stats.bugs.total }}</span>
                            </div>
                            <div class="flex items-center justify-between mt-2 text-xs text-gray-400">
                                <span>已关闭 {{ stats.bugs.closed }}</span>
                            </div>
                        </div>
                    </div>
                    <div class="mt-3 pt-3 border-t border-gray-100">
                        <a class="text-xs text-blue-500 hover:text-blue-700 cursor-pointer flex items-center gap-1" @click="goToWorkItems('bugs')">
                            查看全部缺陷 <ArrowRight :size="12" />
                        </a>
                    </div>
                </div>
            </div>

            <!-- Projects -->
            <div class="bg-white rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-3">
                        <h3 class="text-base font-medium text-gray-800">项目</h3>
                        <div class="flex items-center gap-2">
                            <Filter :size="14" class="text-gray-400" />
                            <vort-select v-model="selectedIterationId" placeholder="迭代筛选" clearable style="width: 140px" @change="loadData">
                                <vort-select-option v-for="i in iterations" :key="i.id" :value="i.id">{{ i.name }}</vort-select-option>
                            </vort-select>
                            <vort-select v-model="selectedVersionId" placeholder="版本筛选" clearable style="width: 140px" @change="loadData">
                                <vort-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.name }}</vort-select-option>
                            </vort-select>
                        </div>
                    </div>
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
                        class="border border-gray-100 rounded-xl p-5 hover:shadow-md transition-all cursor-pointer group relative bg-gray-50/30"
                        @click="handleViewProject(p)"
                    >
                        <div class="flex items-start justify-between mb-2">
                            <div class="flex items-center gap-2 min-w-0 flex-1">
                                <div class="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                                    {{ (p.name || '?')[0] }}
                                </div>
                                <h4 class="font-medium text-gray-800 truncate">{{ p.name }}</h4>
                            </div>
                            <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2" @click.stop>
                                <vort-tooltip title="编辑">
                                    <a class="text-gray-400 hover:text-blue-600 cursor-pointer" @click="handleEditProject(p)">
                                        <Settings :size="14" />
                                    </a>
                                </vort-tooltip>
                                <vort-popconfirm title="确认删除该项目？" @confirm="handleDeleteProject(p)">
                                    <a class="text-gray-400 hover:text-red-500 cursor-pointer">
                                        <Trash2 :size="14" />
                                    </a>
                                </vort-popconfirm>
                            </div>
                        </div>
                        <p class="text-xs text-gray-400 line-clamp-2 mb-3">{{ p.description || '暂无描述' }}</p>

                        <div class="flex items-center gap-2 text-xs flex-wrap mb-3">
                            <vort-tag v-if="p.start_date || p.end_date" size="small" color="green">
                                <Calendar :size="10" class="mr-0.5 inline" />
                                {{ formatDate(p.start_date) }} ~ {{ formatDate(p.end_date) }}
                            </vort-tag>
                            <vort-tag v-if="p.product" size="small" color="default">{{ p.product }}</vort-tag>
                            <vort-tag v-if="p.version" size="small" color="blue">v{{ p.version }}</vort-tag>
                        </div>

                        <div v-if="p.owner_id" class="flex items-center gap-1.5 text-xs text-gray-500 mb-3">
                            <User :size="12" class="text-gray-400" />
                            <span>{{ getMemberNameById(p.owner_id) || p.owner_id }}</span>
                        </div>

                        <div class="pt-3 border-t border-gray-100">
                            <div v-if="projectRepos(p.id).length > 0" class="space-y-2">
                                <div class="text-xs text-gray-500">关联仓库 {{ projectRepos(p.id).length }}</div>
                                <div class="flex flex-wrap gap-1.5">
                                    <vort-tag
                                        v-for="repo in projectRepos(p.id).slice(0, 3)"
                                        :key="repo.id"
                                        size="small"
                                        color="processing"
                                    >
                                        {{ repo.name }}
                                    </vort-tag>
                                    <span v-if="projectRepos(p.id).length > 3" class="text-xs text-gray-400">
                                        +{{ projectRepos(p.id).length - 3 }}
                                    </span>
                                </div>
                            </div>
                            <div v-else class="text-xs text-gray-300">未关联仓库</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Active Iterations -->
            <div class="bg-white rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-base font-medium text-gray-800">
                        <Repeat :size="16" class="inline mr-1.5 text-blue-500" />当前进行中的迭代
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
                        <vort-table-column label="标题" prop="name" :width="200">
                            <template #default="{ row }">
                                <a class="text-sm text-blue-600 hover:underline cursor-pointer" @click.stop="goToIterationDetail(row.id)">
                                    {{ row.name }}
                                </a>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="状态" :width="100">
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
                        <vort-table-column label="预估工时" :width="100">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-600">
                                    {{ row.estimate_hours ? `${row.estimate_hours}h` : '-' }}
                                </span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="目标" :min-width="200">
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
            <vort-form ref="formRef" :model="currentProject" :rules="projectValidationSchema" label-width="80px">
                <vort-form-item label="项目名称" name="name" required has-feedback>
                    <vort-input v-model="currentProject.name" placeholder="请输入项目名称" />
                </vort-form-item>
                <vort-form-item label="产品" name="product">
                    <vort-input v-model="currentProject.product" placeholder="产品名称（可选）" />
                </vort-form-item>
                <vort-form-item label="迭代" name="iteration">
                    <vort-input v-model="currentProject.iteration" placeholder="迭代名称（可选）" />
                </vort-form-item>
                <vort-form-item label="版本" name="version">
                    <vort-input v-model="currentProject.version" placeholder="版本号（可选）" />
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

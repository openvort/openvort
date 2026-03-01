<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { FolderKanban, ListChecks, CheckSquare, Bug, Plus, Settings, Trash2 } from "lucide-vue-next";
import {
    getVortflowStats, getVortflowProjects, createVortflowProject,
    updateVortflowProject, deleteVortflowProject,
    getVortgitRepos,
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
const loading = ref(true);
const stats = ref<DashboardStats>({ stories: { total: 0, done: 0 }, tasks: { total: 0, done: 0 }, bugs: { total: 0, closed: 0 } });
const projects = ref<ProjectItem[]>([]);
const projectRepoMap = ref<Record<string, VortgitRepoItem[]>>({});

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

const loadData = async () => {
    loading.value = true;
    try {
        const [statsRes, projectsRes] = await Promise.all([
            getVortflowStats(), getVortflowProjects(),
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
const formLoading = ref(false);

const handleAddProject = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增项目";
    currentProject.value = {};
    drawerVisible.value = true;
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
};

const handleViewProject = (p: ProjectItem) => {
    router.push(`/vortflow/projects/${p.id}`);
};

const handleSaveProject = async () => {
    const r = currentProject.value;
    if (!r.name?.trim()) return;
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

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <vort-spin :spinning="loading">
            <!-- Stats -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="bg-white rounded-xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                                <ListChecks :size="16" class="text-blue-600" />
                            </div>
                            <span class="text-sm text-gray-500">需求</span>
                        </div>
                        <span class="text-2xl font-bold text-gray-800">{{ stats.stories.total }}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs text-gray-400">
                        <span>已完成 {{ stats.stories.done }}</span>
                        <span>{{ storyProgress }}%</span>
                    </div>
                    <div class="mt-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div class="h-full bg-blue-500 rounded-full transition-all" :style="{ width: storyProgress + '%' }" />
                    </div>
                </div>

                <div class="bg-white rounded-xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-lg bg-green-50 flex items-center justify-center">
                                <CheckSquare :size="16" class="text-green-600" />
                            </div>
                            <span class="text-sm text-gray-500">任务</span>
                        </div>
                        <span class="text-2xl font-bold text-gray-800">{{ stats.tasks.total }}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs text-gray-400">
                        <span>已完成 {{ stats.tasks.done }}</span>
                        <span>{{ taskProgress }}%</span>
                    </div>
                    <div class="mt-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div class="h-full bg-green-500 rounded-full transition-all" :style="{ width: taskProgress + '%' }" />
                    </div>
                </div>

                <div class="bg-white rounded-xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center">
                                <Bug :size="16" class="text-red-600" />
                            </div>
                            <span class="text-sm text-gray-500">缺陷</span>
                        </div>
                        <span class="text-2xl font-bold text-gray-800">{{ stats.bugs.total }}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs text-gray-400">
                        <span>已关闭 {{ stats.bugs.closed }}</span>
                        <span>{{ bugCloseRate }}%</span>
                    </div>
                    <div class="mt-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div class="h-full bg-red-500 rounded-full transition-all" :style="{ width: bugCloseRate + '%' }" />
                    </div>
                </div>
            </div>

            <!-- Projects -->
            <div class="bg-white rounded-xl p-6 mt-4">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-base font-medium text-gray-800">项目</h3>
                    <vort-button variant="primary" @click="handleAddProject">
                        <Plus :size="14" class="mr-1" /> 新增项目
                    </vort-button>
                </div>
                <div v-if="projects.length === 0" class="text-center py-12 text-gray-400">
                    <FolderKanban :size="48" class="mx-auto mb-3 text-gray-300" />
                    <p>暂无项目，点击上方按钮创建第一个项目</p>
                </div>
                <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div v-for="p in projects" :key="p.id"
                        class="border rounded-lg p-4 hover:shadow-sm transition-shadow cursor-pointer group relative"
                        @click="handleViewProject(p)"
                    >
                        <div class="flex items-start justify-between">
                            <h4 class="font-medium text-gray-800 mb-1">{{ p.name }}</h4>
                            <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity" @click.stop>
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
                        <div class="flex items-center gap-2 text-xs text-gray-400 flex-wrap">
                            <vort-tag v-if="p.product" size="small" color="default">{{ p.product }}</vort-tag>
                            <vort-tag v-if="p.iteration" size="small" color="blue">{{ p.iteration }}</vort-tag>
                            <vort-tag v-if="p.version" size="small" color="green">v{{ p.version }}</vort-tag>
                            <span v-if="p.start_date" class="text-xs text-gray-300">
                                {{ p.start_date.split('T')[0] }} ~ {{ p.end_date ? p.end_date.split('T')[0] : '未定' }}
                            </span>
                        </div>
                        <div class="mt-3 pt-3 border-t border-gray-100">
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
        </vort-spin>

        <!-- Project Drawer -->
        <vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="600">
            <vort-form label-width="80px">
                <vort-form-item label="项目名称" required>
                    <vort-input v-model="currentProject.name" placeholder="请输入项目名称" />
                </vort-form-item>
                <vort-form-item label="产品">
                    <vort-input v-model="currentProject.product" placeholder="产品名称（可选）" />
                </vort-form-item>
                <vort-form-item label="迭代">
                    <vort-input v-model="currentProject.iteration" placeholder="迭代名称（可选）" />
                </vort-form-item>
                <vort-form-item label="版本">
                    <vort-input v-model="currentProject.version" placeholder="版本号（可选）" />
                </vort-form-item>
                <vort-form-item label="开始日期">
                    <vort-date-picker v-model="currentProject.start_date" value-format="YYYY-MM-DD" placeholder="请选择开始日期" class="w-full" />
                </vort-form-item>
                <vort-form-item label="结束日期">
                    <vort-date-picker v-model="currentProject.end_date" value-format="YYYY-MM-DD" placeholder="请选择结束日期" class="w-full" />
                </vort-form-item>
                <vort-form-item label="描述">
                    <vort-textarea v-model="currentProject.description" placeholder="请输入项目描述" :rows="4" />
                </vort-form-item>
            </vort-form>
            <div class="flex justify-end gap-3 mt-6">
                <vort-button @click="drawerVisible = false">取消</vort-button>
                <vort-button variant="primary" :loading="formLoading" @click="handleSaveProject">确定</vort-button>
            </div>
        </vort-drawer>
    </div>
</template>

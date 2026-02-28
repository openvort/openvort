<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { FolderKanban, ListChecks, CheckSquare, Bug } from "lucide-vue-next";
import { getVortflowStats, getVortflowProjects } from "@/api";

interface DashboardStats {
    stories: { total: number; done: number };
    tasks: { total: number; done: number };
    bugs: { total: number; closed: number };
}

const loading = ref(true);
const stats = ref<DashboardStats>({ stories: { total: 0, done: 0 }, tasks: { total: 0, done: 0 }, bugs: { total: 0, closed: 0 } });
const projects = ref<any[]>([]);

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

const loadData = async () => {
    loading.value = true;
    try {
        const [statsRes, projectsRes] = await Promise.all([
            getVortflowStats(),
            getVortflowProjects(),
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
    } catch {
        // silent
    } finally {
        loading.value = false;
    }
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
                </div>
                <div v-if="projects.length === 0" class="text-center py-12 text-gray-400">
                    <FolderKanban :size="48" class="mx-auto mb-3 text-gray-300" />
                    <p>暂无项目，通过 AI 助手对话创建第一个项目</p>
                </div>
                <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div v-for="p in projects" :key="p.id" class="border rounded-lg p-4 hover:shadow-sm transition-shadow">
                        <h4 class="font-medium text-gray-800 mb-1">{{ p.name }}</h4>
                        <p class="text-xs text-gray-400 line-clamp-2 mb-3">{{ p.description || '暂无描述' }}</p>
                        <div class="flex items-center gap-2 text-xs text-gray-400">
                            <vort-tag v-if="p.iteration" size="small" color="blue">{{ p.iteration }}</vort-tag>
                            <vort-tag v-if="p.version" size="small" color="green">v{{ p.version }}</vort-tag>
                        </div>
                    </div>
                </div>
            </div>
        </vort-spin>
    </div>
</template>

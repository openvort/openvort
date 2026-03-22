<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { getVortflowStats, getVortflowProjects } from "@/api";
import { BookOpen, CheckSquare, Bug, FolderOpen, ArrowRight } from "lucide-vue-next";

const router = useRouter();

const loading = ref(true);
const stats = ref({ stories: { total: 0, done: 0 }, tasks: { total: 0, done: 0 }, bugs: { total: 0, closed: 0 } });
const projectCount = ref(0);

const storyProgress = computed(() => stats.value.stories.total ? Math.round((stats.value.stories.done / stats.value.stories.total) * 100) : 0);
const taskProgress = computed(() => stats.value.tasks.total ? Math.round((stats.value.tasks.done / stats.value.tasks.total) * 100) : 0);
const bugProgress = computed(() => stats.value.bugs.total ? Math.round((stats.value.bugs.closed / stats.value.bugs.total) * 100) : 0);

onMounted(async () => {
    try {
        const [statsRes, projectsRes] = await Promise.all([
            getVortflowStats(),
            getVortflowProjects(),
        ]);
        if (statsRes) Object.assign(stats.value, statsRes);
        if (projectsRes) projectCount.value = (projectsRes as any)?.items?.length || 0;
    } catch { /* ignore */ }
    finally { loading.value = false; }
});

const items = computed(() => [
    {
        label: "项目", icon: FolderOpen, total: projectCount.value, done: null, progress: null,
        color: "text-indigo-600", bg: "bg-indigo-50", progressColor: "", path: "/vortflow/board",
    },
    {
        label: "需求", icon: BookOpen, total: stats.value.stories.total, done: stats.value.stories.done, progress: storyProgress.value,
        color: "text-blue-600", bg: "bg-blue-50", progressColor: "bg-blue-500", path: "/vortflow/stories",
    },
    {
        label: "任务", icon: CheckSquare, total: stats.value.tasks.total, done: stats.value.tasks.done, progress: taskProgress.value,
        color: "text-emerald-600", bg: "bg-emerald-50", progressColor: "bg-emerald-500", path: "/vortflow/tasks",
    },
    {
        label: "缺陷", icon: Bug, total: stats.value.bugs.total, done: stats.value.bugs.closed, progress: bugProgress.value,
        color: "text-rose-600", bg: "bg-rose-50", progressColor: "bg-rose-500", path: "/vortflow/bugs",
    },
]);
</script>

<template>
    <vort-card :shadow="false" title="项目管理概览">
        <template #extra>
            <a class="text-xs text-blue-600 cursor-pointer flex items-center gap-0.5 hover:text-blue-700" @click="router.push('/vortflow/board')">
                查看看板 <ArrowRight :size="12" />
            </a>
        </template>
        <VortSpin :spinning="loading">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div
                    v-for="item in items" :key="item.label"
                    class="group rounded-xl p-4 cursor-pointer transition-all duration-200 hover:shadow-sm border border-gray-100 hover:border-transparent"
                    :class="item.bg + '/30'"
                    @click="router.push(item.path)"
                >
                    <div class="flex items-center gap-2 mb-3">
                        <div class="w-8 h-8 rounded-lg flex items-center justify-center" :class="item.bg">
                            <component :is="item.icon" :size="16" :class="item.color" />
                        </div>
                        <span class="text-sm font-medium text-gray-700">{{ item.label }}</span>
                    </div>
                    <p class="text-2xl font-bold text-gray-800 mb-1">{{ item.total }}</p>
                    <template v-if="item.progress !== null">
                        <div class="flex items-center justify-between text-xs text-gray-400 mb-1.5">
                            <span>已完成 {{ item.done }}</span>
                            <span>{{ item.progress }}%</span>
                        </div>
                        <div class="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                                class="h-full rounded-full transition-all duration-500"
                                :class="item.progressColor"
                                :style="{ width: item.progress + '%' }"
                            />
                        </div>
                    </template>
                    <template v-else>
                        <span class="text-xs text-gray-400">进行中的项目</span>
                    </template>
                </div>
            </div>
        </VortSpin>
    </vort-card>
</template>

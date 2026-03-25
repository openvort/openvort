<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ChevronDown, ChevronRight, Layers, Loader2, Repeat } from "lucide-vue-next";
import PopoverSelect from "@/components/vort-biz/popover-select/PopoverSelect.vue";
import { getVortflowIterations } from "@/api/vortflow";
import type { VortFlowProject } from "@/stores/modules/vortflow";

interface Props {
    projects: VortFlowProject[];
    selectedId: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
    "update:selectedId": [value: string];
}>();

const route = useRoute();
const router = useRouter();

const dropdownOpen = ref(false);
const searchKeyword = ref("");

const expandedProjectId = ref<string | null>(null);
const projectIterations = ref<Record<string, any[]>>({});
const loadingIterations = ref<Record<string, boolean>>({});

const iterStatusLabel: Record<string, string> = {
    planning: "规划中", active: "进行中", completed: "已完成",
};
const iterStatusColor: Record<string, string> = {
    planning: "#9ca3af", active: "#3b82f6", completed: "#22c55e",
};

const selectedProject = computed(() =>
    props.projects.find(p => p.id === props.selectedId) ?? null
);

const displayName = computed(() =>
    selectedProject.value?.name || "全部项目"
);

const filteredProjects = computed(() => {
    const kw = searchKeyword.value.trim().toLowerCase();
    if (!kw) return props.projects;
    return props.projects.filter(p => p.name.toLowerCase().includes(kw));
});

const toggleIterations = async (projectId: string, event: Event) => {
    event.stopPropagation();
    if (expandedProjectId.value === projectId) {
        expandedProjectId.value = null;
        return;
    }
    expandedProjectId.value = projectId;
    if (projectIterations.value[projectId]) return;

    loadingIterations.value[projectId] = true;
    try {
        const res: any = await getVortflowIterations({ project_id: projectId, page_size: 50 });
        projectIterations.value[projectId] = res.items || [];
    } catch {
        projectIterations.value[projectId] = [];
    } finally {
        loadingIterations.value[projectId] = false;
    }
};

const selectIteration = (projectId: string, iterationId: string) => {
    emit("update:selectedId", projectId);
    dropdownOpen.value = false;
    router.push(`/vortflow/iterations/${iterationId}`);
};

const selectProject = (id: string) => {
    emit("update:selectedId", id);
    dropdownOpen.value = false;
    if (route.name === "vortflow-project-detail" && id) {
        router.push(`/vortflow/projects/${id}`);
    }
};

const goToBoard = () => {
    router.push("/vortflow/board");
};

const goToProjectDetail = () => {
    if (props.selectedId) {
        router.push(`/vortflow/projects/${props.selectedId}`);
    } else {
        goToBoard();
    }
};

const formatDate = (dateStr?: string) => {
    if (!dateStr) return "";
    return dateStr.slice(0, 10);
};

const getWorkItemCount = (p: VortFlowProject) => {
    return (p.story_count ?? 0) + (p.task_count ?? 0) + (p.bug_count ?? 0);
};
</script>

<template>
    <div class="project-breadcrumb">
        <button type="button" class="breadcrumb-prefix" @click="goToBoard">
            <Layers :size="16" />
            <span>项目</span>
        </button>

        <span class="breadcrumb-sep">/</span>

        <button type="button" class="breadcrumb-name" @click="goToProjectDetail">
            {{ displayName }}
        </button>

        <PopoverSelect
            v-model:open="dropdownOpen"
            v-model:keyword="searchKeyword"
            :show-search="true"
            search-placeholder="搜索项目..."
            :dropdown-width="380"
            :dropdown-max-height="400"
            :bordered="false"
            placement="bottomLeft"
        >
            <template #trigger>
                <button
                    type="button"
                    class="breadcrumb-arrow"
                    :class="{ 'is-open': dropdownOpen }"
                    @click.stop="dropdownOpen = !dropdownOpen"
                >
                    <ChevronDown
                        :size="14"
                        :class="{ 'rotate-180': dropdownOpen }"
                    />
                </button>
            </template>

            <div class="py-1">
                <div
                    class="project-row"
                    :class="{ 'is-active': !props.selectedId }"
                    @click.stop="selectProject('')"
                >
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center shrink-0">
                            <Layers :size="16" class="text-gray-400" />
                        </div>
                        <div class="min-w-0">
                            <div class="text-sm font-medium text-gray-800 truncate">全部项目</div>
                        </div>
                    </div>
                    <span v-if="!props.selectedId" class="text-blue-500 text-sm shrink-0">&#10003;</span>
                </div>

                <div v-if="filteredProjects.length" class="border-t border-gray-100 my-1" />

                <div v-for="project in filteredProjects" :key="project.id">
                    <div
                        class="project-row"
                        :class="{ 'is-active': props.selectedId === project.id }"
                        @click.stop="selectProject(project.id)"
                    >
                        <div class="flex items-center gap-3 min-w-0 flex-1">
                            <div class="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center shrink-0">
                                <Layers :size="16" class="text-amber-500" />
                            </div>
                            <div class="min-w-0 flex-1">
                                <div class="text-sm font-medium text-gray-800 truncate">{{ project.name }}</div>
                                <div class="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                                    <span v-if="project.story_count != null">{{ project.story_count }} 需求</span>
                                    <span>{{ getWorkItemCount(project) }} 工作项</span>
                                    <span v-if="project.created_at">{{ formatDate(project.created_at) }}</span>
                                </div>
                            </div>
                        </div>
                        <div class="flex items-center gap-1 shrink-0">
                            <span v-if="props.selectedId === project.id" class="text-blue-500 text-sm">&#10003;</span>
                            <button
                                type="button"
                                class="iter-expand-btn"
                                :class="{ 'is-expanded': expandedProjectId === project.id }"
                                @click.stop="toggleIterations(project.id, $event)"
                            >
                                <Loader2 v-if="loadingIterations[project.id]" :size="14" class="animate-spin" />
                                <ChevronRight v-else :size="14" />
                            </button>
                        </div>
                    </div>

                    <div v-if="expandedProjectId === project.id" class="iter-list">
                        <template v-if="loadingIterations[project.id]">
                            <div class="iter-empty">
                                <Loader2 :size="14" class="animate-spin text-gray-300" />
                                <span>加载中...</span>
                            </div>
                        </template>
                        <template v-else-if="projectIterations[project.id]?.length">
                            <div
                                v-for="iter in projectIterations[project.id]"
                                :key="iter.id"
                                class="iter-row"
                                @click.stop="selectIteration(project.id, iter.id)"
                            >
                                <Repeat :size="13" class="text-gray-400 shrink-0" />
                                <span class="iter-name">{{ iter.name }}</span>
                                <span
                                    class="iter-status"
                                    :style="{ color: iterStatusColor[iter.status] || '#9ca3af' }"
                                >{{ iterStatusLabel[iter.status] || iter.status }}</span>
                            </div>
                        </template>
                        <template v-else>
                            <div class="iter-empty">暂无迭代</div>
                        </template>
                    </div>
                </div>

                <div v-if="!filteredProjects.length" class="px-4 py-6 text-center text-sm text-gray-400">
                    未找到匹配的项目
                </div>
            </div>
        </PopoverSelect>
    </div>
</template>

<style scoped>
.project-breadcrumb {
    display: inline-flex;
    align-items: center;
    gap: 0;
    font-size: 14px;
    white-space: nowrap;
}

.breadcrumb-prefix {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-radius: 6px;
    color: #888;
    font-size: 14px;
    transition: color 0.2s, background 0.2s;
}

.breadcrumb-prefix:hover {
    color: var(--vort-primary, #1456f0);
    background: rgba(0, 0, 0, 0.04);
}

.breadcrumb-sep {
    color: #ccc;
    margin: 0 2px;
    user-select: none;
}

.breadcrumb-name {
    display: inline-flex;
    align-items: center;
    padding: 6px 8px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    color: #374151;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: background 0.2s;
    margin-right: 6px;
}

.breadcrumb-name:hover {
    background: rgba(0, 0, 0, 0.04);
}

.breadcrumb-arrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    background: rgba(0, 0, 0, 0.04);
    cursor: pointer;
    border-radius: 4px;
    color: #aaa;
    transition: color 0.2s, background 0.2s;
}

.breadcrumb-arrow:hover,
.breadcrumb-arrow.is-open {
    color: var(--vort-primary, #1456f0);
    background: rgba(0, 0, 0, 0.08);
}

.breadcrumb-arrow svg {
    transition: transform 0.2s;
}

.project-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 12px;
    margin: 0 4px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s ease;
}

.project-row:hover {
    background: rgba(0, 0, 0, 0.04);
}

.project-row.is-active {
    background: #f1f5f9;
}

.iter-expand-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-radius: 4px;
    color: #9ca3af;
    transition: color 0.15s, background 0.15s, transform 0.2s;
}

.iter-expand-btn:hover {
    color: #6b7280;
    background: rgba(0, 0, 0, 0.06);
}

.iter-expand-btn.is-expanded {
    color: var(--vort-primary, #1456f0);
}

.iter-expand-btn.is-expanded svg:not(.animate-spin) {
    transform: rotate(90deg);
}

.iter-list {
    padding: 2px 0 4px 0;
    margin: 0 4px;
}

.iter-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px 6px 48px;
    border-radius: 5px;
    cursor: pointer;
    transition: background-color 0.15s;
    font-size: 12px;
}

.iter-row:hover {
    background: rgba(0, 0, 0, 0.04);
}

.iter-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #4b5563;
}

.iter-status {
    font-size: 11px;
    flex-shrink: 0;
}

.iter-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 12px 8px 48px;
    font-size: 12px;
    color: #9ca3af;
}
</style>

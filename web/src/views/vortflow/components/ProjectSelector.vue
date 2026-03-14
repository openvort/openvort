<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ChevronDown, Layers } from "lucide-vue-next";
import PopoverSelect from "@/components/vort-biz/popover-select/PopoverSelect.vue";
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

const isBoard = computed(() => route.name === "vortflow-board");

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

const selectProject = (id: string) => {
    emit("update:selectedId", id);
    dropdownOpen.value = false;
};

const goToBoard = () => {
    router.push("/vortflow/board");
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
    <div v-if="!isBoard" class="project-breadcrumb">
        <button type="button" class="breadcrumb-prefix" @click="goToBoard">
            <Layers :size="16" class="breadcrumb-icon" />
            <span>项目</span>
        </button>
        <span class="breadcrumb-sep">/</span>

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
                    class="breadcrumb-project"
                    :class="{ 'is-open': dropdownOpen }"
                    @click.stop="dropdownOpen = !dropdownOpen"
                >
                    <span class="project-name">{{ displayName }}</span>
                    <ChevronDown
                        :size="14"
                        class="arrow-icon"
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

                <div
                    v-for="project in filteredProjects"
                    :key="project.id"
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
                    <span v-if="props.selectedId === project.id" class="text-blue-500 text-sm shrink-0">&#10003;</span>
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

.breadcrumb-icon {
    color: inherit;
}

.breadcrumb-sep {
    color: #ccc;
    margin: 0 2px;
    user-select: none;
}

.breadcrumb-project {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 8px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-radius: 6px;
    font-size: 14px;
    transition: background 0.2s;
}

.breadcrumb-project:hover,
.breadcrumb-project.is-open {
    background: rgba(0, 0, 0, 0.04);
}

.project-name {
    color: var(--vort-primary, #1456f0);
    font-weight: 500;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.arrow-icon {
    color: #aaa;
    transition: transform 0.2s;
    flex-shrink: 0;
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
</style>

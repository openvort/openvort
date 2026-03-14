<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useVortFlowStore } from "@/stores";
import ProjectSelector from "./ProjectSelector.vue";
import ViewSelector from "./ViewSelector.vue";
import { SYSTEM_VIEWS } from "../composables/useVortFlowViews";
import type { WorkItemType } from "@/components/vort-biz/work-item/WorkItemTable.types";

const route = useRoute();
const store = useVortFlowStore();

const WORK_ITEM_ROUTES: Record<string, WorkItemType> = {
    "vortflow-stories": "需求",
    "vortflow-tasks": "任务",
    "vortflow-bugs": "缺陷",
};

const currentWorkItemType = computed<WorkItemType | null>(() => {
    const name = route.name as string;
    return WORK_ITEM_ROUTES[name] ?? null;
});

const showViewSelector = computed(() => currentWorkItemType.value !== null);

const currentViewId = computed(() => {
    if (!currentWorkItemType.value) return "all";
    return store.getViewId(currentWorkItemType.value);
});

const onViewChange = (viewId: string) => {
    if (currentWorkItemType.value) {
        store.setViewId(currentWorkItemType.value, viewId);
    }
};
</script>

<template>
    <div class="bg-white rounded-xl px-4 py-3 flex items-center justify-between gap-4">
        <ProjectSelector
            :projects="store.projects"
            :selected-id="store.selectedProjectId"
            @update:selected-id="store.setProjectId"
        />

        <div v-if="showViewSelector" class="flex items-center gap-2">
            <ViewSelector
                :views="SYSTEM_VIEWS"
                :selected-id="currentViewId"
                @update:selected-id="onViewChange"
            />
        </div>
    </div>
</template>

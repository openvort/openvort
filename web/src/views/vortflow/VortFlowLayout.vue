<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { useRoute } from "vue-router";
import { useVortFlowStore } from "@/stores";
import VortFlowToolbar from "./components/VortFlowToolbar.vue";
import ViewSidebar from "./components/ViewSidebar.vue";
import { SYSTEM_VIEWS } from "./composables/useVortFlowViews";
import type { WorkItemType } from "@/components/vort-biz/work-item/WorkItemTable.types";

const store = useVortFlowStore();
const route = useRoute();

const sidebarPinned = ref(false);

const WORK_ITEM_ROUTES: Record<string, WorkItemType> = {
    "vortflow-stories": "需求",
    "vortflow-tasks": "任务",
    "vortflow-bugs": "缺陷",
};

const currentWorkItemType = computed<WorkItemType | null>(() => {
    const name = route.name as string;
    return WORK_ITEM_ROUTES[name] ?? null;
});

const showSidebar = computed(() => sidebarPinned.value && currentWorkItemType.value !== null);

const currentViewId = computed(() => {
    if (!currentWorkItemType.value) return "all";
    return store.getViewId(currentWorkItemType.value);
});

const onSidebarSelect = (viewId: string) => {
    if (currentWorkItemType.value) {
        store.setViewId(currentWorkItemType.value, viewId);
    }
};

onMounted(() => {
    if (!store.projectsLoaded) {
        store.loadProjects();
    }
});
</script>

<template>
    <div class="space-y-4">
        <VortFlowToolbar />
        <div class="vortflow-content" :class="{ 'with-sidebar': showSidebar }">
            <ViewSidebar
                v-if="showSidebar"
                :views="SYSTEM_VIEWS"
                :selected-id="currentViewId"
                @select="onSidebarSelect"
                @unpin="sidebarPinned = false"
            />
            <div class="vortflow-main">
                <router-view />
            </div>
        </div>
    </div>
</template>

<style scoped>
.vortflow-content {
    display: flex;
    gap: 16px;
}
.vortflow-content.with-sidebar .vortflow-main {
    flex: 1;
    min-width: 0;
}
.vortflow-main {
    width: 100%;
}
</style>

<script setup lang="ts">
import WorkItemTable from "@/views/vortflow/WorkItemTable.vue";
import { useVortFlowStore } from "@/stores";
import { useVortFlowViews } from "./composables/useVortFlowViews";

const store = useVortFlowStore();
const { activeViewFilters } = useVortFlowViews("任务");
</script>

<template>
    <WorkItemTable
        type="任务"
        page-title="任务管理"
        create-button-text="+ 新建任务"
        create-drawer-title="新建任务"
        detail-drawer-title="任务详情"
        :project-id="store.selectedProjectId"
        :view-filters="activeViewFilters"
        use-api
    />
</template>

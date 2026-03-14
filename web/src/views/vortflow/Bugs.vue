<script setup lang="ts">
import WorkItemTable from "@/views/vortflow/WorkItemTable.vue";
import { useVortFlowStore } from "@/stores";
import { useVortFlowViews } from "./composables/useVortFlowViews";

const store = useVortFlowStore();
const { activeViewFilters } = useVortFlowViews("缺陷");
</script>

<template>
    <WorkItemTable
        type="缺陷"
        page-title="缺陷跟踪"
        create-button-text="+ 新建缺陷"
        create-drawer-title="新建缺陷"
        detail-drawer-title="缺陷详情"
        :project-id="store.selectedProjectId"
        :view-filters="activeViewFilters"
        use-api
    />
</template>

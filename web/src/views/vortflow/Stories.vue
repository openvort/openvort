<script setup lang="ts">
import WorkItemTable from "@/views/vortflow/WorkItemTable.vue";
import { useVortFlowStore } from "@/stores";
import { useVortFlowViews } from "./composables/useVortFlowViews";

const store = useVortFlowStore();
const { activeViewFilters } = useVortFlowViews("需求");
</script>

<template>
    <WorkItemTable
        type="需求"
        page-title="需求列表"
        create-button-text="+ 新建需求"
        create-drawer-title="新建需求"
        detail-drawer-title="需求详情"
        :project-id="store.selectedProjectId"
        :view-filters="activeViewFilters"
        use-api
    />
</template>

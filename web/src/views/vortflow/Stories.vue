<script setup lang="ts">
import WorkItemTable from "@/views/vortflow/WorkItemTable.vue";
</script>

<template>
    <WorkItemTable
        type="需求"
        page-title="需求列表"
        create-button-text="+ 新建需求"
        create-drawer-title="新建需求"
        detail-drawer-title="需求详情"
        use-api
    />
</template>

<script setup lang="ts">
import WorkItemTable from "@/views/vortflow/WorkItemTable.vue";
</script>

<template>
    <WorkItemTable
        type="任务"
        page-title="任务管理"
        create-button-text="+ 新建任务"
        create-drawer-title="新建任务"
        detail-drawer-title="任务详情"
        use-api
    />
</template>

<script setup lang="ts">
import WorkItemTable from "@/views/vortflow/WorkItemTable.vue";
</script>

<template>
    <WorkItemTable
        type="缺陷"
        page-title="缺陷跟踪"
        create-button-text="+ 新建缺陷"
        create-drawer-title="新建缺陷"
        detail-drawer-title="缺陷详情"
        use-api
    />
</template>

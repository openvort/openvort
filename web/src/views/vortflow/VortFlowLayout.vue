<script setup lang="ts">
import { onMounted } from "vue";
import { useVortFlowStore } from "@/stores";
import VortFlowToolbar from "./components/VortFlowToolbar.vue";

const store = useVortFlowStore();

onMounted(() => {
    if (!store.projectsLoaded) {
        store.loadProjects();
    }
});
</script>

<template>
    <div class="space-y-4">
        <VortFlowToolbar />
        <router-view />
    </div>
</template>

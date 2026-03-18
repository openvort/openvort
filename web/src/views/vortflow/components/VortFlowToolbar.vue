<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useVortFlowStore } from "@/stores";
import ProjectSelector from "./ProjectSelector.vue";

const route = useRoute();
const store = useVortFlowStore();

const shouldHideToolbar = computed(() =>
    route.name === "vortflow-board" || route.name === "vortflow-settings"
);
</script>

<template>
    <div v-if="!shouldHideToolbar" class="bg-white rounded-xl px-4 py-3 flex items-center gap-4">
        <ProjectSelector
            :projects="store.projects"
            :selected-id="store.selectedProjectId"
            @update:selected-id="store.setProjectId"
        />
    </div>
</template>

<template>
    <div class="flex items-center gap-1 border-b border-gray-200 px-4 overflow-x-auto" style="-ms-overflow-style: none; scrollbar-width: none;"
    >
        <button
            v-for="view in views"
            :key="view.name"
            class="px-3 py-2 text-sm whitespace-nowrap border-b-2 transition-colors -mb-px"
            :class="activeView === view.name
                ? 'border-blue-600 text-blue-600 font-medium'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
            @click="$emit('switch', view.name)"
        >
            {{ view.name }}
        </button>
    </div>
</template>

<script setup lang="ts">
import type { JenkinsView } from "../types";

defineProps<{
    views: JenkinsView[];
    activeView: string;
}>();

defineEmits<{
    (e: "switch", viewName: string): void;
}>();
</script>

<template>
    <span class="inline-flex items-center justify-center w-5 h-5">
        <span v-if="status.animating" class="relative flex h-3 w-3">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" :class="pingClass"></span>
            <span class="relative inline-flex rounded-full h-3 w-3" :class="dotClass"></span>
        </span>
        <span v-else class="inline-flex rounded-full h-3 w-3" :class="dotClass"></span>
    </span>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { getColorStatus } from "../types";

const props = defineProps<{ color: string }>();

const status = computed(() => getColorStatus(props.color));

const dotClass = computed(() => {
    switch (status.value.variant) {
        case "success": return "bg-green-500";
        case "error": return "bg-red-500";
        case "warning": return "bg-yellow-500";
        default: return "bg-gray-400";
    }
});

const pingClass = computed(() => {
    switch (status.value.variant) {
        case "success": return "bg-green-400";
        case "error": return "bg-red-400";
        case "warning": return "bg-yellow-400";
        default: return "bg-gray-300";
    }
});
</script>

<script setup lang="ts">
import aiEmployeeBadgeUrl from "@/assets/brand/ai-employee-badge.png";

withDefaults(defineProps<{
    size?: "sm" | "md";
}>(), {
    size: "sm",
});
</script>

<template>
    <img
        :src="aiEmployeeBadgeUrl"
        alt="AI 员工"
        class="inline-block select-none"
        :class="size === 'md' ? 'h-8 w-auto' : 'h-5 w-auto'"
    />
</template>

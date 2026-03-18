<script setup lang="ts">
withDefaults(defineProps<{
    size?: number;
    animated?: boolean;
}>(), {
    size: 24,
    animated: true,
});
</script>

<template>
    <svg
        class="ai-icon"
        :class="{ 'ai-icon-animated': animated }"
        :width="size"
        :height="size"
        viewBox="0 0 24 24"
        fill="none"
    >
        <path
            class="ai-icon-main"
            d="M12 3L13.8 9.2L20 12L13.8 14.8L12 21L10.2 14.8L4 12L10.2 9.2Z"
            fill="currentColor"
        />
        <path
            class="ai-icon-s1"
            d="M18.5 1.5L19.3 4.3L22 5.5L19.3 6.7L18.5 9.5L17.7 6.7L15 5.5L17.7 4.3Z"
            fill="currentColor"
        />
        <path
            class="ai-icon-s2"
            d="M6 16L6.6 18L8.5 19L6.6 20L6 22L5.4 20L3.5 19L5.4 18Z"
            fill="currentColor"
        />
        <g class="ai-icon-orbit">
            <circle cx="19" cy="14" r="1.1" fill="currentColor" />
        </g>
    </svg>
</template>

<style scoped>
.ai-icon {
    overflow: visible;
}

.ai-icon path,
.ai-icon circle {
    transform-box: fill-box;
    transform-origin: center;
}

.ai-icon-s1 { opacity: 0.8; }
.ai-icon-s2 { opacity: 0.65; }
.ai-icon-orbit circle { opacity: 0.5; }

/* Animations only when .ai-icon-animated */
.ai-icon-animated .ai-icon-main {
    animation: ai-main-pulse 3s ease-in-out infinite;
}
.ai-icon-animated .ai-icon-s1 {
    animation: ai-sparkle-blink 2.6s ease-in-out 0.3s infinite;
}
.ai-icon-animated .ai-icon-s2 {
    animation: ai-sparkle-blink 2.6s ease-in-out 0.9s infinite;
}
.ai-icon-animated .ai-icon-orbit {
    transform-origin: 12px 12px;
    animation: ai-orbit-spin 5s linear infinite;
}
.ai-icon-animated .ai-icon-orbit circle {
    animation: ai-dot-pulse 2s ease-in-out infinite;
}

@keyframes ai-main-pulse {
    0%, 100% { transform: scale(1) rotate(0deg); opacity: 1; }
    50% { transform: scale(1.08) rotate(6deg); opacity: 0.9; }
}
@keyframes ai-sparkle-blink {
    0%, 100% { transform: scale(1); opacity: 0.8; }
    25% { transform: scale(0.5); opacity: 0.2; }
    55% { transform: scale(1.15); opacity: 1; }
}
@keyframes ai-orbit-spin {
    to { transform: rotate(360deg); }
}
@keyframes ai-dot-pulse {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 0.9; }
}
</style>

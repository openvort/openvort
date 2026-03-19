<script setup lang="ts">
import logoUrl from "@/assets/vortmall-ai-logo.svg?url";

withDefaults(defineProps<{
    size?: number;
    animated?: boolean;
}>(), {
    size: 24,
    animated: true,
});
</script>

<template>
    <div
        class="ai-icon"
        :class="{ 'ai-icon-animated': animated }"
        :style="{ width: size + 'px', height: size + 'px' }"
    >
        <div class="ai-icon-spinner">
            <img :src="logoUrl" class="ai-icon-img" draggable="false" />
        </div>
        <div class="ai-icon-shimmer" />
    </div>
</template>

<style scoped>
.ai-icon {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    overflow: visible;
}

.ai-icon-spinner {
    width: 100%;
    height: 100%;
    border-radius: 50%;
    overflow: hidden;
}

.ai-icon-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    pointer-events: none;
    display: block;
}

.ai-icon-shimmer {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    overflow: hidden;
    pointer-events: none;
}
.ai-icon-shimmer::after {
    content: "";
    position: absolute;
    top: -60%;
    left: -120%;
    width: 50%;
    height: 220%;
    background: linear-gradient(
        105deg,
        transparent 0%,
        rgba(255, 255, 255, 0.35) 50%,
        transparent 100%
    );
    transform: skewX(-18deg);
}

.ai-icon-animated .ai-icon-spinner {
    animation: ai-icon-spin 10s linear infinite;
}

.ai-icon-animated .ai-icon-shimmer::after {
    animation: ai-icon-shimmer 5s ease-in-out 1.5s infinite;
}

.ai-icon:hover .ai-icon-spinner {
    animation-duration: 3s;
}

@keyframes ai-icon-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

@keyframes ai-icon-shimmer {
    0%, 100% { left: -120%; opacity: 0; }
    10% { opacity: 1; }
    55% { left: 200%; opacity: 0; }
}
</style>

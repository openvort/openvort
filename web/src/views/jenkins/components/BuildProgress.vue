<template>
    <div
        class="flex items-center gap-2 mt-1 cursor-pointer group"
        @click.stop="$emit('click')"
    >
        <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden min-w-[80px] max-w-[200px]">
            <div
                class="h-full rounded-full transition-all duration-1000 ease-linear relative overflow-hidden bg-blue-500"
                :style="{ width: `${progress}%` }"
            >
                <div class="absolute inset-0 shimmer" />
            </div>
        </div>
        <span class="text-xs text-gray-400 group-hover:text-blue-600 whitespace-nowrap shrink-0">
            构建中
        </span>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";

const props = defineProps<{
    timestamp: number;
    estimatedDuration: number;
}>();

defineEmits<{
    (e: "click"): void;
}>();

const now = ref(Date.now());
let timer: ReturnType<typeof setInterval> | null = null;

const indeterminate = computed(() => !props.estimatedDuration || props.estimatedDuration <= 0);

const progress = computed(() => {
    if (indeterminate.value) return 30;
    const elapsed = now.value - props.timestamp;
    return Math.min(99, Math.max(0, Math.floor((elapsed / props.estimatedDuration) * 100)));
});

function startTimer() {
    stopTimer();
    timer = setInterval(() => { now.value = Date.now(); }, 1000);
}

function stopTimer() {
    if (timer) { clearInterval(timer); timer = null; }
}

onMounted(startTimer);
onUnmounted(stopTimer);

watch(() => props.timestamp, () => { now.value = Date.now(); });
</script>

<style scoped>
.shimmer {
    background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(255, 255, 255, 0.4) 50%,
        transparent 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
</style>

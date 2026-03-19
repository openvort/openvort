<template>
    <div
        class="flex items-center gap-2 mt-1 cursor-pointer group"
        @click.stop="$emit('click')"
    >
        <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden min-w-[80px]">
            <div
                class="h-full bg-blue-500 rounded-full transition-all duration-1000 ease-linear"
                :style="{ width: `${progress}%` }"
            />
        </div>
        <span class="text-xs text-gray-400 group-hover:text-blue-600 whitespace-nowrap shrink-0">
            #{{ buildNumber }}
        </span>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";

const props = defineProps<{
    timestamp: number;
    estimatedDuration: number;
    buildNumber: number;
}>();

defineEmits<{
    (e: "click"): void;
}>();

const now = ref(Date.now());
let timer: ReturnType<typeof setInterval> | null = null;

const progress = computed(() => {
    if (!props.timestamp || !props.estimatedDuration || props.estimatedDuration <= 0) return 0;
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

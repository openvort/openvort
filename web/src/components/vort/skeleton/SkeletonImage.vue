<script setup lang="ts">
import { computed } from "vue";

defineOptions({ name: "VortSkeletonImage" });

/**
 * Vort Skeleton Image - 骨架屏图片占位组件
 */

interface Props {
    /** 是否显示动画效果 */
    active?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    active: false
});

// 样式计算
const imageClass = computed(() => {
    const classes = ["vort-skeleton-image"];
    if (props.active) classes.push("vort-skeleton-image-active");
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div :class="imageClass">
        <svg viewBox="0 0 1098 1024" xmlns="http://www.w3.org/2000/svg" class="vort-skeleton-image-svg">
            <path
                d="M365.714286 329.142857q0 45.714286-32.036571 77.677714t-77.677714 32.036571-77.677714-32.036571-32.036571-77.677714 32.036571-77.677714 77.677714-32.036571 77.677714 32.036571 32.036571 77.677714zM950.857143 548.571429l0 256-804.571429 0 0-109.714286 182.857143-182.857143 91.428571 91.428571 292.571429-292.571429zM1005.714286 146.285714l-914.285714 0q-7.460571 0-12.873143 5.412571t-5.412571 12.873143l0 694.857143q0 7.460571 5.412571 12.873143t12.873143 5.412571l914.285714 0q7.460571 0 12.873143-5.412571t5.412571-12.873143l0-694.857143q0-7.460571-5.412571-12.873143t-12.873143-5.412571zM1097.142857 164.571429l0 694.857143q0 37.741714-26.843429 64.585143t-64.585143 26.843429l-914.285714 0q-37.741714 0-64.585143-26.843429t-26.843429-64.585143l0-694.857143q0-37.741714 26.843429-64.585143t64.585143-26.843429l914.285714 0q37.741714 0 64.585143 26.843429t26.843429 64.585143z"
                fill="currentColor"
            />
        </svg>
    </div>
</template>

<style scoped>
.vort-skeleton-image {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 96px;
    height: 96px;
    background: rgba(0, 0, 0, 0.06);
    border-radius: 6px;
    vertical-align: top;
}

.vort-skeleton-image-svg {
    width: 48px;
    height: 48px;
    color: #bfbfbf;
}

/* 动画效果 */
.vort-skeleton-image-active {
    background: linear-gradient(90deg, rgba(0, 0, 0, 0.06) 25%, rgba(0, 0, 0, 0.15) 37%, rgba(0, 0, 0, 0.06) 63%);
    background-size: 400% 100%;
    animation: vort-skeleton-loading 1.4s ease infinite;
}

@keyframes vort-skeleton-loading {
    0% {
        background-position: 100% 50%;
    }
    100% {
        background-position: 0 50%;
    }
}
</style>

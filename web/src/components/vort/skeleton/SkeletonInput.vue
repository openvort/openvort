<script setup lang="ts">
import { computed } from "vue";

defineOptions({ name: "VortSkeletonInput" });

/**
 * Vort Skeleton Input - 骨架屏输入框占位组件
 */

type InputSize = "large" | "small" | "default";

interface Props {
    /** 是否显示动画效果 */
    active?: boolean;
    /** 是否为块级元素 */
    block?: boolean;
    /** 输入框大小 */
    size?: InputSize;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    active: false,
    block: false,
    size: "default"
});

// 尺寸配置
const sizeConfig = computed(() => {
    const configs = {
        large: { height: 40, minWidth: 200 },
        default: { height: 32, minWidth: 160 },
        small: { height: 24, minWidth: 120 }
    };
    return configs[props.size];
});

// 样式计算
const inputClass = computed(() => {
    const classes = ["vort-skeleton-input", `vort-skeleton-input-${props.size}`];
    if (props.block) classes.push("vort-skeleton-input-block");
    if (props.active) classes.push("vort-skeleton-input-active");
    if (props.class) classes.push(props.class);
    return classes;
});

const inputStyle = computed(() => ({
    height: `${sizeConfig.value.height}px`,
    minWidth: props.block ? undefined : `${sizeConfig.value.minWidth}px`
}));
</script>

<template>
    <span :class="inputClass" :style="inputStyle" />
</template>

<style scoped>
.vort-skeleton-input {
    display: inline-block;
    vertical-align: top;
    background: rgba(0, 0, 0, 0.06);
    border-radius: 6px;
}

/* 块级 */
.vort-skeleton-input-block {
    display: block;
    width: 100%;
}

/* 动画效果 */
.vort-skeleton-input-active {
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

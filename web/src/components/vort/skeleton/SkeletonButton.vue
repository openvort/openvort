<script setup lang="ts">
import { computed } from "vue";

defineOptions({ name: "VortSkeletonButton" });

/**
 * Vort Skeleton Button - 骨架屏按钮占位组件
 */

type ButtonSize = "large" | "small" | "default";
type ButtonShape = "default" | "circle" | "round" | "square";

interface Props {
    /** 是否显示动画效果 */
    active?: boolean;
    /** 是否为块级元素 */
    block?: boolean;
    /** 按钮大小 */
    size?: ButtonSize;
    /** 按钮形状 */
    shape?: ButtonShape;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    active: false,
    block: false,
    size: "default",
    shape: "default"
});

// 尺寸配置
const sizeConfig = computed(() => {
    const configs = {
        large: { height: 40, minWidth: 64, padding: "0 15px" },
        default: { height: 32, minWidth: 64, padding: "0 15px" },
        small: { height: 24, minWidth: 48, padding: "0 7px" }
    };
    return configs[props.size];
});

// 样式计算
const buttonClass = computed(() => {
    const classes = ["vort-skeleton-button", `vort-skeleton-button-${props.size}`, `vort-skeleton-button-${props.shape}`];
    if (props.block) classes.push("vort-skeleton-button-block");
    if (props.active) classes.push("vort-skeleton-button-active");
    if (props.class) classes.push(props.class);
    return classes;
});

const buttonStyle = computed(() => {
    const config = sizeConfig.value;
    const isCircle = props.shape === "circle";

    return {
        height: `${config.height}px`,
        width: isCircle ? `${config.height}px` : undefined,
        minWidth: isCircle ? undefined : `${config.minWidth}px`
    };
});
</script>

<template>
    <span :class="buttonClass" :style="buttonStyle" />
</template>

<style scoped>
.vort-skeleton-button {
    display: inline-block;
    vertical-align: top;
    background: rgba(0, 0, 0, 0.06);
    border-radius: 6px;
}

/* 形状 */
.vort-skeleton-button-circle {
    border-radius: 50%;
}

.vort-skeleton-button-round {
    border-radius: 32px;
}

.vort-skeleton-button-square {
    border-radius: 6px;
}

/* 块级 */
.vort-skeleton-button-block {
    display: block;
    width: 100%;
}

/* 动画效果 */
.vort-skeleton-button-active {
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

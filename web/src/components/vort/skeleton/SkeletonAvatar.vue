<script setup lang="ts">
import { computed } from "vue";

defineOptions({ name: "VortSkeletonAvatar" });

/**
 * Vort Skeleton Avatar - 骨架屏头像占位组件
 */

type AvatarSize = "large" | "small" | "default" | number;
type AvatarShape = "circle" | "square";

interface Props {
    /** 是否显示动画效果 */
    active?: boolean;
    /** 头像大小 */
    size?: AvatarSize;
    /** 头像形状 */
    shape?: AvatarShape;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    active: false,
    size: "default",
    shape: "circle"
});

// 尺寸配置
const sizeValue = computed(() => {
    if (typeof props.size === "number") {
        return props.size;
    }
    const sizes = {
        large: 40,
        default: 32,
        small: 24
    };
    return sizes[props.size];
});

// 样式计算
const avatarClass = computed(() => {
    const classes = ["vort-skeleton-avatar", `vort-skeleton-avatar-${props.shape}`];
    if (typeof props.size !== "number") classes.push(`vort-skeleton-avatar-${props.size}`);
    if (props.active) classes.push("vort-skeleton-avatar-active");
    if (props.class) classes.push(props.class);
    return classes;
});

const avatarStyle = computed(() => ({
    width: `${sizeValue.value}px`,
    height: `${sizeValue.value}px`,
    lineHeight: `${sizeValue.value}px`
}));
</script>

<template>
    <span :class="avatarClass" :style="avatarStyle" />
</template>

<style scoped>
.vort-skeleton-avatar {
    display: inline-block;
    vertical-align: top;
    background: rgba(0, 0, 0, 0.06);
}

/* 形状 */
.vort-skeleton-avatar-circle {
    border-radius: 50%;
}

.vort-skeleton-avatar-square {
    border-radius: 6px;
}

/* 动画效果 */
.vort-skeleton-avatar-active {
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

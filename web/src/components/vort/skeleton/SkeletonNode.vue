<script setup lang="ts">
import { computed } from "vue";

defineOptions({ name: "VortSkeletonNode" });

/**
 * Vort Skeleton Node - 骨架屏自定义节点占位组件
 *
 * 提供一个灵活的占位容器，可以通过插槽自定义内容
 */

interface Props {
    /** 是否显示动画效果 */
    active?: boolean;
    /** 是否为块级元素 */
    block?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    active: false,
    block: false
});

const slots = defineSlots<{
    default?(): unknown;
}>();

// 样式计算
const nodeClass = computed(() => {
    const classes = ["vort-skeleton-node"];
    if (props.block) classes.push("vort-skeleton-node-block");
    if (props.active) classes.push("vort-skeleton-node-active");
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div :class="nodeClass">
        <slot>
            <!-- 默认显示一个方形占位 -->
            <span class="vort-skeleton-node-content" />
        </slot>
    </div>
</template>

<style scoped>
.vort-skeleton-node {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    vertical-align: top;
}

.vort-skeleton-node-block {
    display: flex;
    width: 100%;
}

.vort-skeleton-node-content {
    display: block;
    width: 64px;
    height: 64px;
    background: rgba(0, 0, 0, 0.06);
    border-radius: 6px;
}

/* 动画效果 */
.vort-skeleton-node-active .vort-skeleton-node-content {
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

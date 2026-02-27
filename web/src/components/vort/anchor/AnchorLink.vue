<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, type Ref, type ComputedRef } from "vue";

defineOptions({ name: "VortAnchorLink" });

/**
 * Vort AnchorLink - 锚点链接子组件
 *
 * 用于在 Anchor 组件中定义锚点链接
 */

interface Props {
    /** 锚点链接标题 */
    title?: string;
    /** 锚点链接地址 */
    href: string;
    /** 自定义类名 */
    class?: string;
}

const props = defineProps<Props>();

// 注入锚点上下文
const anchor = inject<{
    activeLink: Ref<string>;
    registerLink: (href: string) => void;
    unregisterLink: (href: string) => void;
    handleClick: (e: MouseEvent, href: string) => void;
    direction: ComputedRef<"vertical" | "horizontal">;
}>("anchor");

// 是否激活
const isActive = computed(() => anchor?.activeLink.value === props.href);

// 处理点击
const handleClick = (e: MouseEvent) => {
    e.preventDefault();
    anchor?.handleClick(e, props.href);
};

// 组合样式
const classes = computed(() => {
    const arr = ["vort-anchor-link"];
    if (isActive.value) arr.push("vort-anchor-link--active");
    if (props.class) arr.push(props.class);
    return arr;
});

onMounted(() => {
    anchor?.registerLink(props.href);
});

onUnmounted(() => {
    anchor?.unregisterLink(props.href);
});
</script>

<template>
    <div :class="classes" :data-href="href">
        <a class="vort-anchor-link__title" :href="href" :title="title" @click="handleClick">
            <slot>{{ title }}</slot>
        </a>
        <!-- 子链接插槽 -->
        <div v-if="$slots['sub-link']" class="vort-anchor-link__children">
            <slot name="sub-link" />
        </div>
    </div>
</template>

<style scoped>
.vort-anchor-link {
    padding: 4px 0;
}

.vort-anchor-link__title {
    display: inline-block;
    color: var(--vort-text-secondary);
    text-decoration: none;
    transition: color 0.2s;
    line-height: 1.5;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.vort-anchor-link__title:hover {
    color: var(--vort-primary);
}

.vort-anchor-link--active > .vort-anchor-link__title {
    color: var(--vort-primary);
    font-weight: 500;
}

/* 子链接 */
.vort-anchor-link__children {
    padding-left: 16px;
}
</style>

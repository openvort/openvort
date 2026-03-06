<script setup lang="ts">
import { computed, useSlots } from "vue";

defineOptions({ name: "VortCard" });

/** Vort Card - 卡片容器组件 */

interface Props {
    /** 自定义类名 */
    class?: string;
    /** 卡片标题 */
    title?: string;
    /** 标题描述，显示在标题后面 */
    desc?: string;
    /** 是否有边框 */
    bordered?: boolean;
    /** 是否有阴影 */
    shadow?: boolean;
    /** 内边距大小 */
    padding?: "none" | "small" | "default" | "large";
}

const props = withDefaults(defineProps<Props>(), {
    bordered: false,
    shadow: true,
    padding: "default"
});

const slots = useSlots();

// 是否显示头部区域（有 title 或 extra 时显示）
const showHead = computed(() => {
    return props.title || slots.title || slots.extra;
});

// ========== 类名计算 ==========

const cardClasses = computed(() => {
    const classes = ["vort-card"];
    if (props.bordered) classes.push("vort-card-bordered");
    if (props.shadow) classes.push("vort-card-shadow");
    if (props.class) classes.push(props.class);
    return classes;
});

const headClasses = computed(() => {
    const classes = ["vort-card-head"];
    if (props.padding) classes.push(`vort-card-head-padding-${props.padding}`);
    return classes;
});

const bodyClasses = computed(() => {
    const classes = ["vort-card-body"];
    if (props.padding) classes.push(`vort-card-body-padding-${props.padding}`);
    return classes;
});
</script>

<template>
    <div :class="cardClasses">
        <!-- 头部区域 -->
        <div v-if="showHead" :class="headClasses">
            <div class="vort-card-head-wrapper">
                <div class="vort-card-head-title">
                    <slot name="title">{{ title }}</slot>
                    <span v-if="desc" class="vort-card-head-desc">{{ desc }}</span>
                </div>
                <div v-if="$slots.extra" class="vort-card-extra">
                    <slot name="extra" />
                </div>
            </div>
        </div>
        <!-- 内容区域 -->
        <div :class="bodyClasses">
            <slot />
        </div>
    </div>
</template>

<style scoped>
.vort-card {
    background: var(--vort-layout-container-bg, #fff);
    border-radius: var(--vort-layout-radius, 8px);
    box-sizing: border-box;
    width: 100%;
}

/* 阴影 */
.vort-card-shadow {
    box-shadow: var(--vort-layout-shadow, 0 1px 2px 0 rgba(0, 0, 0, 0.03));
}

/* 边框 */
.vort-card-bordered {
    border: 1px solid var(--vort-border-color, #f0f0f0);
}

/* ========== 头部区域 ========== */
.vort-card-head {
    border-bottom: 1px solid var(--vort-border-color, #f0f0f0);
}

.vort-card-head-wrapper {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
}

.vort-card-head-title {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    overflow: hidden;
    font-weight: 600;
    font-size: 16px;
    color: rgba(0, 0, 0, 0.88);
    white-space: nowrap;
    text-overflow: ellipsis;
}

.vort-card-head-desc {
    font-weight: 400;
    font-size: 14px;
    color: rgba(0, 0, 0, 0.45);
}

.vort-card-extra {
    flex-shrink: 0;
    color: rgba(0, 0, 0, 0.65);
    font-size: 14px;
}

/* 头部内边距 */
.vort-card-head-padding-none {
    padding: 0;
}

.vort-card-head-padding-small {
    padding: 8px 16px;
}

.vort-card-head-padding-default {
    padding: 12px 20px;
}

.vort-card-head-padding-large {
    padding: 16px 24px;
}

/* ========== 内容区域 ========== */
.vort-card-body-padding-none {
    padding: 0;
}

.vort-card-body-padding-small {
    padding: 12px 16px;
}

.vort-card-body-padding-default {
    padding: 16px 20px;
}

.vort-card-body-padding-large {
    padding: 24px;
}
</style>

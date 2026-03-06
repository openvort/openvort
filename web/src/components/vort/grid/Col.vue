<script setup lang="ts">
import { computed, inject } from "vue";
import { rowContextKey } from "./types";

defineOptions({ name: "VortCol" });

/** Vort Col - 栅格列组件 */

type ColSpan = number | string;

interface ColSize {
    span?: ColSpan;
    offset?: number;
    order?: number;
    pull?: number;
    push?: number;
}

interface Props {
    /** 栅格占位格数，0 时相当于 display: none */
    span?: ColSpan;
    /** 栅格左侧的间隔格数 */
    offset?: number;
    /** 栅格顺序 */
    order?: number;
    /** 栅格向左移动格数 */
    pull?: number;
    /** 栅格向右移动格数 */
    push?: number;
    /** flex 布局属性 */
    flex?: string | number;
    /** 响应式 - xs 屏幕 < 576px */
    xs?: ColSpan | ColSize;
    /** 响应式 - sm 屏幕 ≥ 576px */
    sm?: ColSpan | ColSize;
    /** 响应式 - md 屏幕 ≥ 768px */
    md?: ColSpan | ColSize;
    /** 响应式 - lg 屏幕 ≥ 992px */
    lg?: ColSpan | ColSize;
    /** 响应式 - xl 屏幕 ≥ 1200px */
    xl?: ColSpan | ColSize;
    /** 响应式 - xxl 屏幕 ≥ 1600px */
    xxl?: ColSpan | ColSize;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    span: undefined,
    offset: 0,
    order: 0,
    pull: 0,
    push: 0
});

// 获取 Row 上下文
const rowContext = inject(rowContextKey, null);

// 计算 gutter padding
const gutterPadding = computed(() => {
    if (!rowContext) return 0;
    return rowContext.gutter[0] / 2;
});

// ========== 类名计算 ==========

const colClasses = computed(() => {
    const classes = ["vort-col"];

    // span = 0 隐藏
    const spanNum = typeof props.span === "string" ? parseInt(props.span, 10) : props.span;
    if (spanNum === 0) {
        classes.push("vort-col-hidden");
    }

    if (props.class) classes.push(props.class);
    return classes;
});

// 计算样式
const colStyle = computed(() => {
    const style: Record<string, string> = {};

    // Gutter padding
    if (gutterPadding.value > 0) {
        style.paddingLeft = `${gutterPadding.value}px`;
        style.paddingRight = `${gutterPadding.value}px`;
    }

    // Span 宽度
    const spanNum = typeof props.span === "string" ? parseInt(props.span, 10) : props.span;
    if (spanNum !== undefined && spanNum > 0 && spanNum < 24) {
        const spanWidth = `${(spanNum / 24) * 100}%`;
        style.flex = `0 0 ${spanWidth}`;
        style.maxWidth = spanWidth;
    } else if (spanNum === 24) {
        style.flex = "0 0 100%";
        style.maxWidth = "100%";
    }

    // Flex 属性
    if (props.flex !== undefined) {
        if (typeof props.flex === "number") {
            style.flex = `${props.flex} ${props.flex} auto`;
        } else {
            style.flex = props.flex;
        }
    }

    // Offset
    if (props.offset && props.offset > 0) {
        style.marginLeft = `${(props.offset / 24) * 100}%`;
    }

    // Order
    if (props.order && props.order !== 0) {
        style.order = String(props.order);
    }

    // Pull
    if (props.pull && props.pull > 0) {
        style.right = `${(props.pull / 24) * 100}%`;
        style.position = "relative";
    }

    // Push
    if (props.push && props.push > 0) {
        style.left = `${(props.push / 24) * 100}%`;
        style.position = "relative";
    }

    return style;
});
</script>

<template>
    <div :class="colClasses" :style="colStyle">
        <slot />
    </div>
</template>

<style scoped>
.vort-col {
    position: relative;
    min-height: 1px;
    box-sizing: border-box;
}

.vort-col-hidden {
    display: none;
}
</style>

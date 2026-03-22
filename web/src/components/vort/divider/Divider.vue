<script setup lang="ts">
import { computed, useSlots } from "vue";

defineOptions({ name: "VortDivider" });

/** Vort Divider - 分割线组件 */

type DividerType = "horizontal" | "vertical";
type Orientation = "left" | "right" | "center";

interface Props {
    /** 分割线方向 */
    type?: DividerType;
    /** 是否虚线 */
    dashed?: boolean;
    /** 文字位置 */
    orientation?: Orientation;
    /** 文字距离两侧的距离，取值 0 ~ 1 表示百分比 */
    orientationMargin?: string | number;
    /** 分割线是否是纯净的（不带文字时样式） */
    plain?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    type: "horizontal",
    dashed: false,
    orientation: "center",
    plain: false
});

const slots = useSlots();
const hasContent = computed(() => !!slots.default);

// 计算 orientationMargin
const marginStyle = computed(() => {
    if (!hasContent.value || props.type === "vertical") return {};

    const margin = props.orientationMargin;
    if (margin === undefined) {
        // 默认边距
        if (props.orientation === "left") {
            return { "--vort-divider-margin-left": "5%", "--vort-divider-margin-right": "auto" };
        }
        if (props.orientation === "right") {
            return { "--vort-divider-margin-left": "auto", "--vort-divider-margin-right": "5%" };
        }
        return {};
    }

    const marginValue = typeof margin === "number" ? `${margin}px` : margin;

    if (props.orientation === "left") {
        return { "--vort-divider-margin-left": marginValue, "--vort-divider-margin-right": "auto" };
    }
    if (props.orientation === "right") {
        return { "--vort-divider-margin-left": "auto", "--vort-divider-margin-right": marginValue };
    }
    return {};
});

// ========== 类名计算 ==========

const dividerClasses = computed(() => {
    const classes = ["vort-divider"];
    classes.push(props.type === "horizontal" ? "vort-divider-horizontal" : "vort-divider-vertical");
    if (props.dashed) classes.push("vort-divider-dashed");
    if (hasContent.value) {
        classes.push("vort-divider-with-text");
        classes.push(`vort-divider-with-text-${props.orientation}`);
    }
    if (props.plain) classes.push("vort-divider-plain");
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div :class="dividerClasses" :style="marginStyle" role="separator" :aria-orientation="type">
        <span v-if="hasContent && type === 'horizontal'" class="vort-divider-inner-text">
            <slot />
        </span>
    </div>
</template>

<style scoped>
.vort-divider {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    font-size: 14px;
    line-height: 1.5714285714285714;
    list-style: none;
    border-block-start: 1px solid var(--vort-border, rgba(5, 5, 5, 0.06));
}

/* 水平分割线 */
.vort-divider-horizontal {
    display: flex;
    clear: both;
    width: 100%;
    min-width: 100%;
    margin: 24px 0;
}

/* 垂直分割线 */
.vort-divider-vertical {
    position: relative;
    display: inline-block;
    height: 0.9em;
    margin: 0 8px;
    vertical-align: middle;
    border-top: 0;
    border-inline-start: 1px solid var(--vort-border, rgba(5, 5, 5, 0.06));
}

/* 虚线 */
.vort-divider-dashed {
    background: none;
    border-color: var(--vort-border, rgba(5, 5, 5, 0.06));
    border-style: dashed;
    border-width: 1px 0 0;
}

.vort-divider-vertical.vort-divider-dashed {
    border-width: 0 0 0 1px;
}

/* 带文字的分割线 */
.vort-divider-with-text {
    display: flex;
    align-items: center;
    margin: 16px 0;
    color: rgba(0, 0, 0, 0.88);
    font-weight: 500;
    font-size: 16px;
    white-space: nowrap;
    text-align: center;
    border-block-start: 0;
}

.vort-divider-with-text::before,
.vort-divider-with-text::after {
    position: relative;
    width: 50%;
    border-block-start: 1px solid transparent;
    border-block-start-color: inherit;
    border-block-end: 0;
    transform: translateY(50%);
    content: "";
}

.vort-divider-with-text.vort-divider-dashed::before,
.vort-divider-with-text.vort-divider-dashed::after {
    border-style: dashed none none;
}

/* 文字位置 - 左 */
.vort-divider-with-text-left::before {
    width: var(--vort-divider-margin-left, 5%);
}

.vort-divider-with-text-left::after {
    width: var(--vort-divider-margin-right, 95%);
}

/* 文字位置 - 右 */
.vort-divider-with-text-right::before {
    width: var(--vort-divider-margin-left, 95%);
}

.vort-divider-with-text-right::after {
    width: var(--vort-divider-margin-right, 5%);
}

/* 文字位置 - 中 */
.vort-divider-with-text-center::before,
.vort-divider-with-text-center::after {
    width: 50%;
}

/* 内部文字 */
.vort-divider-inner-text {
    display: inline-block;
    padding: 0 1em;
}

/* 纯净模式 */
.vort-divider-plain {
    font-weight: normal;
    font-size: 14px;
}

/* 继承边框颜色 */
.vort-divider-horizontal::before,
.vort-divider-horizontal::after {
    border-block-start-color: var(--vort-border, rgba(5, 5, 5, 0.06));
}
</style>

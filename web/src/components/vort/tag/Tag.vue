<script setup lang="ts">
import { computed } from "vue";
import { CloseOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortTag" });

/** Vort Tag - 标签组件 */

// 预设状态颜色
type PresetStatusColor = "success" | "processing" | "error" | "warning" | "default";

// 预设颜色名
type PresetColor = "magenta" | "red" | "volcano" | "orange" | "gold" | "lime" | "green" | "cyan" | "teal" | "blue" | "geekblue" | "purple";

interface Props {
    /** 标签色：可以是预设颜色或自定义颜色值 */
    color?: PresetStatusColor | PresetColor | string;
    /** 标签是否可关闭 */
    closable?: boolean;
    /** 是否有边框 */
    bordered?: boolean;
    /** 简易样式（无背景色，仅文字和边框） */
    plain?: boolean;
    /** 白色背景 */
    white?: boolean;
    /** 实心模式（color 作为背景和边框色，文字白色） */
    solid?: boolean;
    /** 尺寸 */
    size?: "small" | "default";
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    closable: false,
    bordered: true,
    plain: false,
    white: false,
    solid: false,
    size: "default"
});

const emit = defineEmits<{
    /** 关闭时触发 */
    close: [e: MouseEvent];
}>();

// 定义插槽类型
defineSlots<{
    /** 默认插槽，标签内容 */
    default?: () => unknown;
    /** 自定义图标 */
    icon?: () => unknown;
    /** 自定义关闭图标 */
    closeIcon?: () => unknown;
}>();

// 预设状态颜色列表
const presetStatusColors: PresetStatusColor[] = ["success", "processing", "error", "warning", "default"];

// 预设颜色列表
const presetColors: PresetColor[] = ["magenta", "red", "volcano", "orange", "gold", "lime", "green", "cyan", "teal", "blue", "geekblue", "purple"];

// 检查是否是预设状态颜色
const isPresetStatusColor = (color: string | undefined): color is PresetStatusColor => {
    return color !== undefined && presetStatusColors.includes(color as PresetStatusColor);
};

// 检查是否是预设颜色
const isPresetColor = (color: string | undefined): color is PresetColor => {
    return color !== undefined && presetColors.includes(color as PresetColor);
};

// 检查是否是自定义颜色（CSS 颜色值）
const isCustomColor = computed(() => {
    if (!props.color) return false;
    return !isPresetStatusColor(props.color) && !isPresetColor(props.color);
});

// ========== 类名计算 ==========

const tagClasses = computed(() => {
    const classes: string[] = ["vort-tag"];

    // 尺寸
    classes.push(props.size === "small" ? "vort-tag-small" : "vort-tag-default");

    // 边框
    if (!props.bordered) classes.push("vort-tag-borderless");

    // 简易样式
    if (props.plain) classes.push("vort-tag-plain");

    // 白色背景
    if (props.white) classes.push("vort-tag-white");

    // 实心模式
    if (props.solid) classes.push("vort-tag-solid");

    // 预设颜色
    if (props.color && !isCustomColor.value) {
        classes.push(`vort-tag-${props.color}`);
    }

    // 自定义颜色
    if (isCustomColor.value) {
        classes.push("vort-tag-custom");
    }

    // 自定义类名
    if (props.class) classes.push(props.class);

    return classes;
});

// 计算自定义颜色的内联样式
const tagStyles = computed(() => {
    if (!isCustomColor.value || !props.color) return {};

    // 白色背景或简易样式：文字和边框使用自定义颜色
    if (props.white || props.plain) {
        return {
            "--_tag-color": props.color,
            "--_tag-bg": props.white ? "#fff" : "transparent",
            "--_tag-border": props.color
        };
    }

    // 默认：自定义颜色作为背景和边框，白色文字
    return {
        "--_tag-color": "#fff",
        "--_tag-bg": props.color,
        "--_tag-border": props.color
    };
});

// 处理关闭
const handleClose = (e: MouseEvent) => {
    e.stopPropagation();
    emit("close", e);
};
</script>

<template>
    <span :class="tagClasses" :style="tagStyles">
        <!-- 图标插槽 -->
        <span v-if="$slots.icon" class="vort-tag-icon">
            <slot name="icon" />
        </span>

        <!-- 内容 -->
        <span class="vort-tag-content">
            <slot />
        </span>

        <!-- 关闭按钮 -->
        <span v-if="closable" class="vort-tag-close" @click="handleClose">
            <slot name="closeIcon">
                <CloseOutlined />
            </slot>
        </span>
    </span>
</template>

<style scoped>
/* ========================================
   CSS Variables（局部变量，可被状态类覆盖）
   ======================================== */

/* ========================================
   基础样式
   ======================================== */
.vort-tag {
    /* 默认样式变量 */
    --_tag-color: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_tag-bg: rgba(0, 0, 0, 0.02);
    --_tag-border: var(--vort-border, #d9d9d9);

    display: inline-flex;
    align-items: center;
    box-sizing: border-box;
    white-space: nowrap;
    border-radius: var(--vort-radius-sm, 4px);
    border: 1px solid var(--_tag-border);
    background: var(--_tag-bg);
    color: var(--_tag-color);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    transition: all var(--vort-duration-normal, 200ms);
}

/* ========================================
   尺寸
   ======================================== */
.vort-tag-default {
    gap: 4px;
    padding: 0 7px;
    font-size: 12px;
    line-height: 20px;
}

.vort-tag-small {
    gap: 2px;
    padding: 0 4px;
    font-size: 12px;
    line-height: 14px;
}

/* ========================================
   Borderless (no visible border)
   ======================================== */
.vort-tag-borderless {
    border: none;
}

/* ========================================
   简易样式（透明背景）
   ======================================== */
.vort-tag-plain {
    --_tag-bg: transparent;
    --_tag-border: currentColor;
}

/* ========================================
   白色背景
   ======================================== */
.vort-tag-white {
    --_tag-bg: #fff;
    --_tag-border: currentColor;
}

/* ========================================
   实心模式
   ======================================== */
.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_tag-border: var(--vort-text, rgba(0, 0, 0, 0.88));
}

/* ========================================
   自定义颜色
   ======================================== */
.vort-tag-custom {
    color: var(--_tag-color);
    background: var(--_tag-bg);
    border-color: var(--_tag-border);
}

/* ========================================
   预设状态颜色 - Success
   ======================================== */
.vort-tag-success {
    --_tag-color: #52c41a;
    --_tag-bg: #f6ffed;
    --_tag-border: #b7eb8f;
}

.vort-tag-success.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #52c41a;
    --_tag-border: #52c41a;
}

/* ========================================
   预设状态颜色 - Processing
   ======================================== */
.vort-tag-processing {
    --_tag-color: var(--vort-primary, #1456f0);
    --_tag-bg: #e6f4ff;
    --_tag-border: var(--vort-primary, #1456f0);
}

.vort-tag-processing.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: var(--vort-primary, #1456f0);
    --_tag-border: var(--vort-primary, #1456f0);
}

/* ========================================
   预设状态颜色 - Error
   ======================================== */
.vort-tag-error {
    --_tag-color: #ff4d4f;
    --_tag-bg: #fff2f0;
    --_tag-border: #ffccc7;
}

.vort-tag-error.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #ff4d4f;
    --_tag-border: #ff4d4f;
}

/* ========================================
   预设状态颜色 - Warning
   ======================================== */
.vort-tag-warning {
    --_tag-color: #faad14;
    --_tag-bg: #fffbe6;
    --_tag-border: #ffe58f;
}

.vort-tag-warning.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #faad14;
    --_tag-border: #faad14;
}

/* ========================================
   预设状态颜色 - Default
   ======================================== */
.vort-tag-default {
    --_tag-color: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_tag-bg: #fafafa;
    --_tag-border: #d9d9d9;
}

.vort-tag-default.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_tag-border: var(--vort-text, rgba(0, 0, 0, 0.88));
}

/* ========================================
   预设颜色 - Magenta
   ======================================== */
.vort-tag-magenta {
    --_tag-color: #c41d7f;
    --_tag-bg: #fff0f6;
    --_tag-border: #ffadd2;
}

.vort-tag-magenta.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #c41d7f;
    --_tag-border: #c41d7f;
}

/* ========================================
   预设颜色 - Red
   ======================================== */
.vort-tag-red {
    --_tag-color: #cf1322;
    --_tag-bg: #fff1f0;
    --_tag-border: #ffa39e;
}

.vort-tag-red.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #cf1322;
    --_tag-border: #cf1322;
}

/* ========================================
   预设颜色 - Volcano
   ======================================== */
.vort-tag-volcano {
    --_tag-color: #d4380d;
    --_tag-bg: #fff2e8;
    --_tag-border: #ffbb96;
}

.vort-tag-volcano.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #d4380d;
    --_tag-border: #d4380d;
}

/* ========================================
   预设颜色 - Orange
   ======================================== */
.vort-tag-orange {
    --_tag-color: #d46b08;
    --_tag-bg: #fff7e6;
    --_tag-border: #ffd591;
}

.vort-tag-orange.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #d46b08;
    --_tag-border: #d46b08;
}

/* ========================================
   预设颜色 - Gold
   ======================================== */
.vort-tag-gold {
    --_tag-color: #d48806;
    --_tag-bg: #fffbe6;
    --_tag-border: #ffe58f;
}

.vort-tag-gold.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #d48806;
    --_tag-border: #d48806;
}

/* ========================================
   预设颜色 - Lime
   ======================================== */
.vort-tag-lime {
    --_tag-color: #7cb305;
    --_tag-bg: #fcffe6;
    --_tag-border: #eaff8f;
}

.vort-tag-lime.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #7cb305;
    --_tag-border: #7cb305;
}

/* ========================================
   预设颜色 - Green
   ======================================== */
.vort-tag-green {
    --_tag-color: #389e0d;
    --_tag-bg: #f6ffed;
    --_tag-border: #b7eb8f;
}

.vort-tag-green.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #389e0d;
    --_tag-border: #389e0d;
}

/* ========================================
   预设颜色 - Cyan
   ======================================== */
.vort-tag-cyan {
    --_tag-color: #08979c;
    --_tag-bg: #e6fffb;
    --_tag-border: #87e8de;
}

.vort-tag-cyan.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #08979c;
    --_tag-border: #08979c;
}

/* ========================================
   预设颜色 - Teal
   ======================================== */
.vort-tag-teal {
    --_tag-color: #31c19e;
    --_tag-bg: #e6f7f3;
    --_tag-border: #7ae3c6;
}

.vort-tag-teal.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #31c19e;
    --_tag-border: #31c19e;
}

/* ========================================
   预设颜色 - Blue
   ======================================== */
.vort-tag-blue {
    --_tag-color: #0958d9;
    --_tag-bg: #e6f4ff;
    --_tag-border: #91caff;
}

.vort-tag-blue.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #0958d9;
    --_tag-border: #0958d9;
}

/* ========================================
   预设颜色 - Geekblue
   ======================================== */
.vort-tag-geekblue {
    --_tag-color: #1d39c4;
    --_tag-bg: #f0f5ff;
    --_tag-border: #adc6ff;
}

.vort-tag-geekblue.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #1d39c4;
    --_tag-border: #1d39c4;
}

/* ========================================
   预设颜色 - Purple
   ======================================== */
.vort-tag-purple {
    --_tag-color: #531dab;
    --_tag-bg: #f9f0ff;
    --_tag-border: #d3adf7;
}

.vort-tag-purple.vort-tag-solid {
    --_tag-color: #fff;
    --_tag-bg: #531dab;
    --_tag-border: #531dab;
}

/* ========================================
   内部元素
   ======================================== */
.vort-tag-icon {
    display: flex;
    align-items: center;
}

.vort-tag-content {
    display: inline-flex;
    align-items: center;
}

.vort-tag-close {
    display: flex;
    align-items: center;
    font-size: 10px;
    cursor: pointer;
    opacity: 0.6;
    transition: opacity var(--vort-transition-colors, 0.1s);
}

.vort-tag-close:hover {
    opacity: 1;
}
</style>

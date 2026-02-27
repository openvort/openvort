<script setup lang="ts">
import { computed, ref } from "vue";
import { LoadingOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortButton" });

/** Vort Button - 按钮组件 */

type ButtonVariant = "primary" | "default" | "dashed" | "text" | "link" | "plain" | "soft";
type ButtonSize = "large" | "middle" | "small";
type ButtonShape = "default" | "round" | "circle";
type ButtonHTMLType = "button" | "submit" | "reset";

interface Props {
    /** 按钮变体（样式类型） */
    variant?: ButtonVariant;
    /** 按钮类型（variant 的别名，方便习惯 type="primary" 的用户） */
    type?: ButtonVariant;
    /** 按钮尺寸 */
    size?: ButtonSize;
    /** 按钮形状 */
    shape?: ButtonShape;
    /** 是否为危险按钮 */
    danger?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否加载中 */
    loading?: boolean;
    /** 是否为幽灵按钮（背景透明） */
    ghost?: boolean;
    /** 将按钮宽度调整为其父宽度 */
    block?: boolean;
    /** 设置按钮的图标组件（仅图标按钮） */
    icon?: boolean;
    /** 原生 type 属性 */
    htmlType?: ButtonHTMLType;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    variant: undefined,
    type: undefined,
    size: "middle",
    shape: "default",
    danger: false,
    disabled: false,
    loading: false,
    ghost: false,
    block: false,
    icon: false,
    htmlType: "button"
});

const emit = defineEmits<{
    click: [event: MouseEvent];
}>();

// 合并 variant 和 type，优先使用 variant，兼容 type 作为别名
const resolvedVariant = computed<ButtonVariant>(() => props.variant ?? props.type ?? "default");

const isDisabled = computed(() => props.disabled || props.loading);

// Soft/Text/Link 不需要点击波纹（光晕）动画
const isWaveDisabled = computed(() => ["text", "link", "soft"].includes(resolvedVariant.value));

// ========== 类名计算（只负责切换状态类名）==========

const buttonClasses = computed(() => {
    const classes = ["vort-btn", `vort-btn-${resolvedVariant.value}`, `vort-btn-${props.size}`];

    // 形状
    if (props.shape !== "default") {
        classes.push(`vort-btn-${props.shape}`);
    }

    // 状态
    if (props.danger) classes.push("vort-btn-danger");
    if (props.ghost) classes.push("vort-btn-ghost");
    if (props.block) classes.push("vort-btn-block");
    if (props.icon) classes.push("vort-btn-icon-only");
    if (props.loading) classes.push("vort-btn-loading");
    if (props.disabled) classes.push("vort-btn-disabled");

    // 自定义类名
    if (props.class) classes.push(props.class);

    return classes;
});

// ========== 波纹动画 ==========
const showWave = ref(false);

const handleClick = (event: MouseEvent) => {
    if (!isDisabled.value) {
        // 触发波纹动画（部分变体不需要）
        if (!isWaveDisabled.value) {
            triggerWave();
        }
        emit("click", event);
    }
};

const triggerWave = () => {
    // 重置动画状态
    showWave.value = false;
    // 使用 requestAnimationFrame 确保 DOM 更新后再触发动画
    requestAnimationFrame(() => {
        showWave.value = true;
    });
};

const onWaveAnimationEnd = () => {
    showWave.value = false;
};
</script>

<template>
    <button :type="htmlType" :class="buttonClasses" :disabled="isDisabled" @click="handleClick">
        <!-- 点击波纹效果 -->
        <span v-if="showWave && !isWaveDisabled" class="vort-btn-wave" @animationend="onWaveAnimationEnd" />

        <!-- Loading 图标 -->
        <Transition name="vort-btn-loading-icon">
            <span v-if="loading" class="vort-btn-loading-icon">
                <LoadingOutlined />
            </span>
        </Transition>

        <!-- 内容插槽 -->
        <slot />
    </button>
</template>

<style scoped>
/* ========================================
   基础样式
   ======================================== */
.vort-btn {
    /* 局部变量 - 可被变体/状态类覆盖 */
    --_bg: #fff;
    --_bg-hover: #fff;
    --_bg-active: #fff;
    --_border-color: var(--vort-border, #d9d9d9);
    --_border-color-hover: var(--vort-primary-hover, #4078f2);
    --_border-color-active: var(--vort-primary-active, #0d3eb8);
    --_text-color: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_text-color-hover: var(--vort-primary-hover, #4078f2);
    --_text-color-active: var(--vort-primary-active, #0d3eb8);
    --_shadow: 0 2px 0 rgba(0, 0, 0, 0.02);
    --_wave-color: var(--vort-primary, #1456f0);

    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-weight: 400;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    border: 1px solid var(--_border-color);
    border-radius: var(--vort-radius, 6px);
    background: var(--_bg);
    color: var(--_text-color);
    box-shadow: var(--_shadow);
    transition:
        background-color var(--vort-transition-colors, 0.1s),
        border-color var(--vort-transition-colors, 0.1s),
        color var(--vort-transition-colors, 0.1s),
        box-shadow var(--vort-transition-colors, 0.1s);
}

.vort-btn:hover:not(.vort-btn-disabled) {
    background: var(--_bg-hover);
    border-color: var(--_border-color-hover);
    color: var(--_text-color-hover);
}

.vort-btn:active:not(.vort-btn-disabled) {
    background: var(--_bg-active);
    border-color: var(--_border-color-active);
    color: var(--_text-color-active);
}

.vort-btn:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

/* ========================================
   尺寸
   ======================================== */
.vort-btn-large {
    height: var(--vort-height-lg, 40px);
    padding: 0 16px;
    font-size: var(--vort-font-size-md, 16px);
    gap: 8px;
}

.vort-btn-middle {
    height: var(--vort-height-md, 32px);
    padding: 0 16px;
    font-size: var(--vort-font-size-sm, 14px);
    gap: 6px;
}

.vort-btn-small {
    height: var(--vort-height-sm, 24px);
    padding: 0 8px;
    font-size: 12px;
    gap: 4px;
}

/* ========================================
   形状 - Round
   ======================================== */
.vort-btn-round.vort-btn-large {
    border-radius: 20px;
}

.vort-btn-round.vort-btn-middle {
    border-radius: 16px;
}

.vort-btn-round.vort-btn-small {
    border-radius: 12px;
}

/* ========================================
   形状 - Circle
   ======================================== */
.vort-btn-circle {
    border-radius: 50%;
    padding: 0;
}

.vort-btn-circle.vort-btn-large {
    width: var(--vort-height-lg, 40px);
    height: var(--vort-height-lg, 40px);
}

.vort-btn-circle.vort-btn-middle {
    width: var(--vort-height-md, 32px);
    height: var(--vort-height-md, 32px);
}

.vort-btn-circle.vort-btn-small {
    width: var(--vort-height-sm, 24px);
    height: var(--vort-height-sm, 24px);
}

/* ========================================
   图标按钮
   ======================================== */
.vort-btn-icon-only {
    padding: 0;
}

.vort-btn-icon-only.vort-btn-large {
    width: var(--vort-height-lg, 40px);
}

.vort-btn-icon-only.vort-btn-middle {
    width: var(--vort-height-md, 32px);
}

.vort-btn-icon-only.vort-btn-small {
    width: var(--vort-height-sm, 24px);
}

/* ========================================
   变体 - Primary（主按钮）
   ======================================== */
.vort-btn-primary {
    --_bg: var(--vort-primary, #1456f0);
    --_bg-hover: var(--vort-primary-hover, #4078f2);
    --_bg-active: var(--vort-primary-active, #0d3eb8);
    --_border-color: var(--vort-primary, #1456f0);
    --_border-color-hover: var(--vort-primary-hover, #4078f2);
    --_border-color-active: var(--vort-primary-active, #0d3eb8);
    --_text-color: #fff;
    --_text-color-hover: #fff;
    --_text-color-active: #fff;
    --_shadow: 0 2px 0 var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
    --_wave-color: var(--vort-primary, #1456f0);
}

/* ========================================
   变体 - Default（默认按钮）
   ======================================== */
.vort-btn-default {
    --_bg: #fff;
    --_bg-hover: #fff;
    --_bg-active: #fff;
    --_border-color: var(--vort-border, #d9d9d9);
    --_border-color-hover: var(--vort-primary-hover, #4078f2);
    --_border-color-active: var(--vort-primary-active, #0d3eb8);
    --_text-color: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_text-color-hover: var(--vort-primary-hover, #4078f2);
    --_text-color-active: var(--vort-primary-active, #0d3eb8);
}

/* ========================================
   变体 - Dashed（虚线按钮）
   ======================================== */
.vort-btn-dashed {
    --_bg: #fff;
    --_border-color: var(--vort-border, #d9d9d9);
    --_border-color-hover: var(--vort-primary-hover, #4078f2);
    --_border-color-active: var(--vort-primary-active, #0d3eb8);
    --_text-color: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_text-color-hover: var(--vort-primary-hover, #4078f2);
    --_text-color-active: var(--vort-primary-active, #0d3eb8);
    border-style: dashed;
}

/* ========================================
   变体 - Text（文本按钮）
   ======================================== */
.vort-btn-text {
    --_bg: transparent;
    --_bg-hover: rgba(0, 0, 0, 0.06);
    --_bg-active: rgba(0, 0, 0, 0.15);
    --_border-color: transparent;
    --_border-color-hover: transparent;
    --_border-color-active: transparent;
    --_text-color: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_text-color-hover: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_text-color-active: var(--vort-text, rgba(0, 0, 0, 0.88));
    --_shadow: none;
}

/* Text 按钮不显示波纹 */
.vort-btn-text .vort-btn-wave {
    display: none;
}

/* ========================================
   变体 - Link（链接按钮）
   ======================================== */
.vort-btn-link {
    --_bg: transparent;
    --_bg-hover: transparent;
    --_bg-active: transparent;
    --_border-color: transparent;
    --_border-color-hover: transparent;
    --_border-color-active: transparent;
    --_text-color: var(--vort-primary, #1456f0);
    --_text-color-hover: var(--vort-primary-hover, #4078f2);
    --_text-color-active: var(--vort-primary-active, #0d3eb8);
    --_shadow: none;
    padding: 0;
    height: auto;
}

/* Link 按钮不显示波纹 */
.vort-btn-link .vort-btn-wave {
    display: none;
}

/* ========================================
   变体 - Plain（朴素按钮）
   ======================================== */
.vort-btn-plain {
    --_bg: var(--vort-primary-bg, #e8f0fe);
    --_bg-hover: var(--vort-primary, #1456f0);
    --_bg-active: var(--vort-primary-active, #0d3eb8);
    --_border-color: var(--vort-primary, #1456f0);
    --_border-color-hover: var(--vort-primary, #1456f0);
    --_border-color-active: var(--vort-primary-active, #0d3eb8);
    --_text-color: var(--vort-primary, #1456f0);
    --_text-color-hover: #fff;
    --_text-color-active: #fff;
    --_shadow: none;
}

/* ========================================
   变体 - Soft（柔和按钮）
   ======================================== */
.vort-btn-soft {
    --_bg: #f5f7fa;
    --_bg-hover: #f0f2f5;
    --_bg-active: #e8eaed;
    --_border-color: transparent;
    --_border-color-hover: transparent;
    --_border-color-active: transparent;
    --_text-color: var(--vort-primary, #1456f0);
    --_text-color-hover: var(--vort-primary, #1456f0);
    --_text-color-active: var(--vort-primary, #1456f0);
    --_shadow: none;
    border-radius: 1px;
    padding: 0 11px;
    font-size: 12px;
}

/* Soft 按钮不显示波纹（点击光晕） */
.vort-btn-soft .vort-btn-wave {
    display: none;
}

/* ========================================
   危险状态
   ======================================== */
.vort-btn-danger {
    --_wave-color: var(--vort-error, #ff4d4f);
}

.vort-btn-danger.vort-btn-primary {
    --_bg: var(--vort-error, #ff4d4f);
    --_bg-hover: var(--vort-error-hover, #ff7875);
    --_bg-active: var(--vort-error-active, #d9363e);
    --_border-color: var(--vort-error, #ff4d4f);
    --_border-color-hover: var(--vort-error-hover, #ff7875);
    --_border-color-active: var(--vort-error-active, #d9363e);
    --_shadow: 0 2px 0 rgba(255, 38, 5, 0.06);
}

.vort-btn-danger.vort-btn-default,
.vort-btn-danger.vort-btn-dashed {
    --_border-color: var(--vort-error, #ff4d4f);
    --_border-color-hover: var(--vort-error-hover, #ff7875);
    --_border-color-active: var(--vort-error-active, #d9363e);
    --_text-color: var(--vort-error, #ff4d4f);
    --_text-color-hover: var(--vort-error-hover, #ff7875);
    --_text-color-active: var(--vort-error-active, #d9363e);
}

.vort-btn-danger.vort-btn-text {
    --_text-color: var(--vort-error, #ff4d4f);
    --_text-color-hover: var(--vort-error, #ff4d4f);
    --_text-color-active: var(--vort-error, #ff4d4f);
    --_bg-hover: var(--vort-error-bg, #fff2f0);
    --_bg-active: var(--vort-error-bg, #fff2f0);
}

.vort-btn-danger.vort-btn-link {
    --_text-color: var(--vort-error, #ff4d4f);
    --_text-color-hover: var(--vort-error-hover, #ff7875);
    --_text-color-active: var(--vort-error-active, #d9363e);
}

.vort-btn-danger.vort-btn-plain {
    --_bg: var(--vort-error-bg, #fff2f0);
    --_bg-hover: var(--vort-error, #ff4d4f);
    --_bg-active: var(--vort-error-active, #d9363e);
    --_border-color: var(--vort-error, #ff4d4f);
    --_border-color-hover: var(--vort-error, #ff4d4f);
    --_border-color-active: var(--vort-error-active, #d9363e);
    --_text-color: var(--vort-error, #ff4d4f);
    --_text-color-hover: #fff;
    --_text-color-active: #fff;
}

.vort-btn-danger.vort-btn-soft {
    --_text-color: var(--vort-error, #ff4d4f);
    --_text-color-hover: var(--vort-error, #ff4d4f);
    --_text-color-active: var(--vort-error, #ff4d4f);
}

/* ========================================
   Ghost 幽灵按钮
   ======================================== */
.vort-btn-ghost {
    --_bg: transparent;
    --_bg-hover: transparent;
    --_bg-active: transparent;
}

.vort-btn-ghost.vort-btn-primary {
    --_border-color: var(--vort-primary, #1456f0);
    --_border-color-hover: var(--vort-primary-hover, #4078f2);
    --_border-color-active: var(--vort-primary-active, #0d3eb8);
    --_text-color: var(--vort-primary, #1456f0);
    --_text-color-hover: var(--vort-primary-hover, #4078f2);
    --_text-color-active: var(--vort-primary-active, #0d3eb8);
}

.vort-btn-ghost.vort-btn-default {
    --_border-color: #fff;
    --_border-color-hover: var(--vort-primary-hover, #4078f2);
    --_border-color-active: var(--vort-primary-active, #0d3eb8);
    --_text-color: #fff;
    --_text-color-hover: var(--vort-primary-hover, #4078f2);
    --_text-color-active: var(--vort-primary-active, #0d3eb8);
}

.vort-btn-ghost.vort-btn-danger,
.vort-btn-ghost.vort-btn-danger.vort-btn-primary {
    --_bg: transparent;
    --_bg-hover: transparent;
    --_bg-active: transparent;
    --_border-color: var(--vort-error, #ff4d4f);
    --_border-color-hover: var(--vort-error-hover, #ff7875);
    --_border-color-active: var(--vort-error-active, #d9363e);
    --_text-color: var(--vort-error, #ff4d4f);
    --_text-color-hover: var(--vort-error-hover, #ff7875);
    --_text-color-active: var(--vort-error-active, #d9363e);
}

/* ========================================
   Block 全宽
   ======================================== */
.vort-btn-block {
    width: 100%;
}

/* ========================================
   Disabled 禁用状态
   ======================================== */
.vort-btn-disabled {
    --_bg: #fff;
    --_bg-hover: #fff;
    --_bg-active: #fff;
    --_border-color: var(--vort-border, #d9d9d9);
    --_border-color-hover: var(--vort-border, #d9d9d9);
    --_border-color-active: var(--vort-border, #d9d9d9);
    --_text-color: rgba(0, 0, 0, 0.25);
    --_text-color-hover: rgba(0, 0, 0, 0.25);
    --_text-color-active: rgba(0, 0, 0, 0.25);
    --_shadow: none;
    cursor: not-allowed;
}

.vort-btn-disabled.vort-btn-text,
.vort-btn-disabled.vort-btn-link {
    --_bg: transparent;
    --_bg-hover: transparent;
    --_bg-active: transparent;
    --_border-color: transparent;
    --_border-color-hover: transparent;
    --_border-color-active: transparent;
}

.vort-btn-disabled.vort-btn-soft {
    --_bg: #f5f7fa;
    --_bg-hover: #f5f7fa;
    --_bg-active: #f5f7fa;
    --_border-color: #f5f7fa;
    --_border-color-hover: #f5f7fa;
    --_border-color-active: #f5f7fa;
}

/* ========================================
   点击波纹动画
   ======================================== */
.vort-btn-wave {
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: transparent;
    box-sizing: border-box;
    pointer-events: none;
    color: var(--_wave-color);
    box-shadow: 0 0 0 0 currentcolor;
    opacity: 0.2;
    animation:
        vort-wave-spread 0.4s var(--vort-ease-out-circ, cubic-bezier(0.08, 0.82, 0.17, 1)),
        vort-wave-fade 2s var(--vort-ease-out-circ, cubic-bezier(0.08, 0.82, 0.17, 1));
    animation-fill-mode: forwards;
}

/* ========================================
   Loading 加载中
   ======================================== */
.vort-btn-loading {
    cursor: default;
    pointer-events: none;
}

.vort-btn-loading-icon {
    display: inline-flex;
    align-items: center;
    width: 22px;
    opacity: 1;
    transform: scale(1);
}

.vort-btn-loading-icon :deep(svg) {
    animation: vort-spin 1s linear infinite;
}

.vort-btn-small .vort-btn-loading-icon {
    width: 18px;
}

.vort-btn-small .vort-btn-loading-icon :deep(svg) {
    width: 12px;
    height: 12px;
}

/* Vue Transition 动画 */
.vort-btn-loading-icon-enter-active,
.vort-btn-loading-icon-leave-active {
    transition: all var(--vort-duration-normal, 200ms) var(--vort-ease-in-out, cubic-bezier(0.645, 0.045, 0.355, 1));
}

.vort-btn-loading-icon-enter-from,
.vort-btn-loading-icon-leave-to {
    width: 0;
    opacity: 0;
    transform: scale(0);
}

/* Spin 动画 */
@keyframes vort-spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}
</style>

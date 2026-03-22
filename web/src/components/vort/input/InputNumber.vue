<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted, useSlots, useAttrs } from "vue";
import type { StyleValue } from "vue";
import { UpOutlined, DownOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortInputNumber", inheritAttrs: false });

/** Vort InputNumber - 数字输入框组件 */

type InputSize = "large" | "middle" | "small";
type InputStatus = "error" | "warning";

interface Props {
    /** 当前值（v-model） */
    modelValue?: number | null;
    /** 默认值 */
    defaultValue?: number;
    /** 最小值 */
    min?: number;
    /** 最大值 */
    max?: number;
    /** 每次改变步数，可以为小数 */
    step?: number | string;
    /** 数值精度（小数位数） */
    precision?: number;
    /** 尺寸 */
    size?: InputSize;
    /** 输入框状态 */
    status?: InputStatus;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否只读 */
    readOnly?: boolean;
    /** 是否有边框 */
    bordered?: boolean;
    /** 输入框占位文本 */
    placeholder?: string;
    /** 自定义类名 */
    class?: string;
    /** 是否隐藏控制按钮 */
    controls?: boolean;
    /** 指定输入框展示值的格式 */
    formatter?: (value: number | string | undefined) => string;
    /** 指定从 formatter 里转换回数字的方式 */
    parser?: (value: string | undefined) => number | string;
    /** 带有前缀图标的 input */
    prefix?: string;
    /** 是否启用键盘快捷行为（上下箭头调整值） */
    keyboard?: boolean;
    /** 是否严格校验，在失焦时校验并矫正数值 */
    stringMode?: boolean;
    /** 紧凑模式，用于 addonBefore/addonAfter 放置 Select 等组件 */
    compact?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    step: 1,
    size: "middle",
    disabled: false,
    readOnly: false,
    bordered: true,
    controls: true,
    keyboard: true,
    stringMode: false,
    compact: false
});

const emit = defineEmits<{
    "update:modelValue": [value: number | null];
    change: [value: number | null];
    step: [value: number | null, info: { offset: number; type: "up" | "down" }];
    focus: [event: FocusEvent];
    blur: [event: FocusEvent];
    pressEnter: [event: KeyboardEvent];
}>();

const attrs = useAttrs();
const slots = useSlots();
const inputRef = ref<HTMLInputElement | null>(null);
const isFocused = ref(false);
const isHovered = ref(false);
const attrsStyle = computed<StyleValue | undefined>(() => attrs.style as StyleValue | undefined);

// 是否有 addon（前置/后置标签）
const hasAddon = computed(() => !!slots.addonBefore || !!slots.addonAfter);

// 内部显示值
const displayValue = ref("");

// 当前数值
const innerValue = ref<number | null>(props.modelValue ?? props.defaultValue ?? null);

// 步进值
const stepNum = computed(() => {
    const s = Number(props.step);
    return isNaN(s) ? 1 : s;
});

// 精度计算
const getPrecision = (num: number): number => {
    const str = String(num);
    const dotIndex = str.indexOf(".");
    return dotIndex > -1 ? str.length - dotIndex - 1 : 0;
};

const precision = computed(() => {
    if (props.precision !== undefined) {
        return props.precision;
    }
    const stepPrecision = getPrecision(stepNum.value);
    const valuePrecision = innerValue.value !== null ? getPrecision(innerValue.value) : 0;
    return Math.max(stepPrecision, valuePrecision);
});

// 格式化数值为显示字符串
const formatValue = (val: number | null): string => {
    if (val === null || val === undefined) return "";
    const numVal = typeof val === "number" ? val : Number(val);
    if (isNaN(numVal)) return "";
    const formatted = precision.value !== undefined ? numVal.toFixed(precision.value) : String(numVal);
    if (props.formatter) return props.formatter(formatted);
    return formatted;
};

// 解析字符串为数值
const parseValue = (str: string): number | null => {
    if (str === "" || str === "-") return null;
    let parsed = str;
    if (props.parser) {
        const result = props.parser(str);
        parsed = String(result);
    }
    parsed = parsed.replace(/[^\d.\-]/g, "");
    const num = parseFloat(parsed);
    return isNaN(num) ? null : num;
};

// 限制数值在 min/max 范围内
const clampValue = (val: number | null): number | null => {
    if (val === null || val === undefined) return null;
    let result = typeof val === "number" ? val : Number(val);
    if (isNaN(result)) return null;
    if (props.min !== undefined && result < props.min) result = props.min;
    if (props.max !== undefined && result > props.max) result = props.max;
    if (precision.value !== undefined) result = parseFloat(result.toFixed(precision.value));
    return result;
};

// 监听 modelValue 变化
watch(
    () => props.modelValue,
    (newVal) => {
        innerValue.value = newVal ?? null;
        if (!isFocused.value) displayValue.value = formatValue(innerValue.value);
    },
    { immediate: true }
);

// 监听 innerValue 变化更新显示值
watch(
    () => innerValue.value,
    (newVal) => {
        if (!isFocused.value) displayValue.value = formatValue(newVal);
    }
);

// 初始化显示值
onMounted(() => {
    displayValue.value = formatValue(innerValue.value);
});

// 是否可以增加
const canIncrease = computed(() => {
    if (props.disabled || props.readOnly) return false;
    if (props.max === undefined) return true;
    return innerValue.value === null || innerValue.value < props.max;
});

// 是否可以减少
const canDecrease = computed(() => {
    if (props.disabled || props.readOnly) return false;
    if (props.min === undefined) return true;
    return innerValue.value === null || innerValue.value > props.min;
});

// ========== 类名计算（只负责切换状态类名）==========

/** Wrapper 类名 */
const wrapperClasses = computed(() => {
    const classes = ["vort-input-number", `vort-input-number-${props.size}`];

    if (props.status) classes.push(`vort-input-number-${props.status}`);
    if (props.disabled) classes.push("vort-input-number-disabled");
    if (!props.bordered) classes.push("vort-input-number-borderless");
    if (hasAddon.value) classes.push("vort-input-number-has-addon");
    if (slots.addonBefore) classes.push("vort-input-number-has-addon-before");
    if (slots.addonAfter) classes.push("vort-input-number-has-addon-after");
    if (props.compact) classes.push("vort-input-number-compact");
    if (isHovered.value || isFocused.value) classes.push("vort-input-number-active");
    if (!hasAddon.value && props.class) classes.push(props.class);

    return classes;
});

/** Addon 外层容器类名 */
const addonWrapperClasses = computed(() => {
    const classes = ["vort-input-number-addon-wrapper"];
    if (props.class) classes.push(props.class);
    return classes;
});

/** addonBefore 类名 */
const addonBeforeClasses = computed(() => {
    const classes = ["vort-input-number-addon", "vort-input-number-addon-before", `vort-input-number-addon-${props.size}`];
    if (props.compact) classes.push("vort-input-number-addon-compact");
    return classes;
});

/** addonAfter 类名 */
const addonAfterClasses = computed(() => {
    const classes = ["vort-input-number-addon", "vort-input-number-addon-after", `vort-input-number-addon-${props.size}`];
    if (props.compact) classes.push("vort-input-number-addon-compact");
    return classes;
});

/** 控制按钮容器类名 */
const controlsClasses = computed(() => {
    const classes = ["vort-input-number-handler-wrap", `vort-input-number-handler-wrap-${props.size}`];
    if (isHovered.value || isFocused.value) classes.push("vort-input-number-handler-wrap-visible");
    return classes;
});

/** 控制按钮类名 */
const getControlBtnClasses = (type: "up" | "down", enabled: boolean) => {
    const classes = ["vort-input-number-handler", `vort-input-number-handler-${type}`];
    if (!enabled) classes.push("vort-input-number-handler-disabled");
    return classes;
};

// ========== 事件处理 ==========

const handleInput = (event: Event) => {
    const target = event.target as HTMLInputElement;
    displayValue.value = target.value;
};

const handleChange = () => {
    const parsed = parseValue(displayValue.value);
    const clamped = clampValue(parsed);
    innerValue.value = clamped;
    displayValue.value = formatValue(clamped);
    emit("update:modelValue", clamped);
    emit("change", clamped);
};

const handleFocus = (event: FocusEvent) => {
    isFocused.value = true;
    if (innerValue.value !== null) displayValue.value = String(innerValue.value);
    emit("focus", event);
};

const handleBlur = (event: FocusEvent) => {
    isFocused.value = false;
    handleChange();
    emit("blur", event);
};

const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === "Enter") {
        handleChange();
        emit("pressEnter", event);
    }
    if (props.keyboard) {
        if (event.key === "ArrowUp") {
            event.preventDefault();
            handleStep("up");
        } else if (event.key === "ArrowDown") {
            event.preventDefault();
            handleStep("down");
        }
    }
};

// 步进操作
const handleStep = (type: "up" | "down") => {
    if (props.disabled || props.readOnly) return;
    if (type === "up" && !canIncrease.value) return;
    if (type === "down" && !canDecrease.value) return;

    const offset = type === "up" ? stepNum.value : -stepNum.value;
    const currentVal = innerValue.value ?? 0;
    const newVal = clampValue(currentVal + offset);

    innerValue.value = newVal;
    displayValue.value = formatValue(newVal);
    emit("update:modelValue", newVal);
    emit("change", newVal);
    emit("step", newVal, { offset, type });
};

// 长按支持
let longPressTimer: ReturnType<typeof setTimeout> | null = null;
let longPressInterval: ReturnType<typeof setInterval> | null = null;

const startLongPress = (type: "up" | "down") => {
    handleStep(type);
    longPressTimer = setTimeout(() => {
        longPressInterval = setInterval(() => handleStep(type), 50);
    }, 300);
};

const stopLongPress = () => {
    if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
    }
    if (longPressInterval) {
        clearInterval(longPressInterval);
        longPressInterval = null;
    }
};

onUnmounted(() => stopLongPress());

const handleMouseEnter = () => {
    isHovered.value = true;
};

const handleMouseLeave = () => {
    isHovered.value = false;
};

const handleWrapperClick = () => {
    if (!props.disabled) inputRef.value?.focus();
};

// 暴露方法
defineExpose({
    input: inputRef,
    focus: () => inputRef.value?.focus(),
    blur: () => inputRef.value?.blur()
});
</script>

<template>
    <!-- 有 addon 时需要外层容器 -->
    <span v-if="hasAddon" :class="addonWrapperClasses" :style="attrsStyle">
        <!-- 前置标签 -->
        <span v-if="$slots.addonBefore" :class="addonBeforeClasses">
            <slot name="addonBefore" />
        </span>

        <!-- 输入框主体 -->
        <span :class="wrapperClasses" @click="handleWrapperClick" @mouseenter="handleMouseEnter" @mouseleave="handleMouseLeave">
            <!-- 前缀 -->
            <span v-if="$slots.prefix || prefix" class="vort-input-number-prefix">
                <slot name="prefix">{{ prefix }}</slot>
            </span>

            <!-- 输入框 -->
            <input
                ref="inputRef"
                type="text"
                inputmode="decimal"
                :value="displayValue"
                class="vort-input-number-input"
                :disabled="disabled"
                :readonly="readOnly"
                :placeholder="placeholder"
                @input="handleInput"
                @change="handleChange"
                @focus="handleFocus"
                @blur="handleBlur"
                @keydown="handleKeydown"
            />

            <!-- 后缀内容 -->
            <span v-if="$slots.suffix" class="vort-input-number-suffix">
                <slot name="suffix" />
            </span>

            <!-- 控制按钮 -->
            <span v-if="controls" :class="controlsClasses">
                <span
                    :class="getControlBtnClasses('up', canIncrease)"
                    role="button"
                    aria-label="Increase Value"
                    @mousedown.prevent="canIncrease && startLongPress('up')"
                    @mouseup="stopLongPress"
                    @mouseleave="stopLongPress"
                >
                    <UpOutlined class="vort-input-number-handler-icon" />
                </span>
                <span
                    :class="getControlBtnClasses('down', canDecrease)"
                    role="button"
                    aria-label="Decrease Value"
                    @mousedown.prevent="canDecrease && startLongPress('down')"
                    @mouseup="stopLongPress"
                    @mouseleave="stopLongPress"
                >
                    <DownOutlined class="vort-input-number-handler-icon" />
                </span>
            </span>
        </span>

        <!-- 后置标签 -->
        <span v-if="$slots.addonAfter" :class="addonAfterClasses">
            <slot name="addonAfter" />
        </span>
    </span>

    <!-- 无 addon 时 -->
    <span v-else :class="wrapperClasses" :style="attrsStyle" @click="handleWrapperClick" @mouseenter="handleMouseEnter" @mouseleave="handleMouseLeave">
        <!-- 前缀 -->
        <span v-if="$slots.prefix || prefix" class="vort-input-number-prefix">
            <slot name="prefix">{{ prefix }}</slot>
        </span>

        <!-- 输入框 -->
        <input
            ref="inputRef"
            type="text"
            inputmode="decimal"
            :value="displayValue"
            class="vort-input-number-input"
            :disabled="disabled"
            :readonly="readOnly"
            :placeholder="placeholder"
            @input="handleInput"
            @change="handleChange"
            @focus="handleFocus"
            @blur="handleBlur"
            @keydown="handleKeydown"
        />

        <!-- 后缀内容 -->
        <span v-if="$slots.suffix" class="vort-input-number-suffix">
            <slot name="suffix" />
        </span>

        <!-- 控制按钮 -->
        <span v-if="controls" :class="controlsClasses">
            <span
                :class="getControlBtnClasses('up', canIncrease)"
                role="button"
                aria-label="Increase Value"
                @mousedown.prevent="canIncrease && startLongPress('up')"
                @mouseup="stopLongPress"
                @mouseleave="stopLongPress"
            >
                <UpOutlined class="vort-input-number-handler-icon" />
            </span>
            <span
                :class="getControlBtnClasses('down', canDecrease)"
                role="button"
                aria-label="Decrease Value"
                @mousedown.prevent="canDecrease && startLongPress('down')"
                @mouseup="stopLongPress"
                @mouseleave="stopLongPress"
            >
                <DownOutlined class="vort-input-number-handler-icon" />
            </span>
        </span>
    </span>
</template>

<style scoped>
/* ========================================
   CSS Variables（局部变量，可被状态类覆盖）
   ======================================== */

/* ========================================
   基础样式 - Wrapper
   ======================================== */
.vort-input-number {
    /* 局部变量 - 可被状态类覆盖 */
    --_border-color: var(--vort-border, #d9d9d9);
    --_focus-color: var(--vort-primary, #1456f0);
    --_focus-shadow: var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
    --_bg-color: #fff;

    position: relative;
    display: inline-flex;
    align-items: center;
    width: 100%;
    border: 1px solid var(--_border-color);
    border-radius: var(--vort-radius, 6px);
    background: var(--_bg-color);
    cursor: text;
    overflow: hidden; /* 防止控制按钮超出圆角边界 */
    transition: var(--vort-transition-all, all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1));
}

/* ========================================
   交互状态 - Hover
   ======================================== */
.vort-input-number:hover:not(.vort-input-number-disabled) {
    border-color: var(--_focus-color);
}

/* ========================================
   交互状态 - Focus
   ======================================== */
.vort-input-number:focus-within:not(.vort-input-number-disabled) {
    border-color: var(--_focus-color);
    box-shadow: 0 0 0 2px var(--_focus-shadow);
}

/* ========================================
   状态覆盖 - Error
   ======================================== */
.vort-input-number-error {
    --_border-color: var(--vort-error, #ff4d4f);
    --_focus-color: var(--vort-error, #ff4d4f);
    --_focus-shadow: rgba(255, 77, 79, 0.06);
}

/* ========================================
   状态覆盖 - Warning
   ======================================== */
.vort-input-number-warning {
    --_border-color: var(--vort-warning, #faad14);
    --_focus-color: var(--vort-warning, #faad14);
    --_focus-shadow: rgba(250, 173, 20, 0.1);
}

/* ========================================
   状态覆盖 - Disabled
   ======================================== */
.vort-input-number-disabled {
    --_bg-color: rgba(0, 0, 0, 0.04);
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: not-allowed;
}

.vort-input-number-disabled .vort-input-number-input {
    cursor: not-allowed;
}

/* ========================================
   状态覆盖 - Borderless
   ======================================== */
.vort-input-number-borderless {
    border-color: transparent;
    background: transparent;
}

.vort-input-number-borderless:hover:not(.vort-input-number-disabled),
.vort-input-number-borderless:focus-within:not(.vort-input-number-disabled) {
    border-color: transparent;
    box-shadow: none;
}

/* ========================================
   尺寸 - Large
   ======================================== */
.vort-input-number-large {
    height: var(--vort-height-lg, 40px);
    font-size: var(--vort-font-size-md, 16px);
}

.vort-input-number-large .vort-input-number-input {
    padding: 0 11px;
}

.vort-input-number-large .vort-input-number-prefix {
    padding-left: 11px;
    padding-right: 7px;
}

.vort-input-number-large .vort-input-number-suffix {
    padding-left: 7px;
    padding-right: 11px;
}

/* ========================================
   尺寸 - Middle（默认）
   ======================================== */
.vort-input-number-middle {
    height: var(--vort-height-md, 32px);
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-input-number-middle .vort-input-number-input {
    padding: 0 11px;
}

.vort-input-number-middle .vort-input-number-prefix {
    padding-left: 11px;
    padding-right: 7px;
}

.vort-input-number-middle .vort-input-number-suffix {
    padding-left: 7px;
    padding-right: 11px;
}

/* ========================================
   尺寸 - Small
   ======================================== */
.vort-input-number-small {
    height: var(--vort-height-sm, 24px);
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-input-number-small .vort-input-number-input {
    padding: 0 7px;
}

.vort-input-number-small .vort-input-number-prefix {
    padding-left: 7px;
    padding-right: 4px;
}

.vort-input-number-small .vort-input-number-suffix {
    padding-left: 4px;
    padding-right: 7px;
}

/* ========================================
   内部元素 - Input
   ======================================== */
.vort-input-number-input {
    flex: 1;
    min-width: 0;
    height: 100%;
    background: transparent;
    border: none;
    outline: none;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-input-number-input::placeholder {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* 有前缀时，input 不需要左 padding */
.vort-input-number:has(.vort-input-number-prefix) .vort-input-number-input {
    padding-left: 0;
}

/* 有后缀时，input 不需要右 padding */
.vort-input-number:has(.vort-input-number-suffix) .vort-input-number-input {
    padding-right: 0;
}

/* ========================================
   内部元素 - 前缀/后缀
   ======================================== */
.vort-input-number-prefix {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

.vort-input-number-suffix {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   控制按钮容器
   ======================================== */
.vort-input-number-handler-wrap {
    position: absolute;
    inset-block: 0;
    right: 0;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    background: #fff;
    border-left: 1px solid var(--vort-border, #d9d9d9);
    border-radius: 0 var(--vort-radius, 6px) var(--vort-radius, 6px) 0;
    opacity: 0;
    transition: opacity var(--vort-duration-normal, 200ms) var(--vort-ease-in-out, cubic-bezier(0.645, 0.045, 0.355, 1));
    transition-delay: var(--vort-duration-normal, 200ms);
}

.vort-input-number-handler-wrap-large {
    width: 22px;
}

.vort-input-number-handler-wrap-middle {
    width: 22px;
}

.vort-input-number-handler-wrap-small {
    width: 18px;
}

/* 显示控制按钮 */
.vort-input-number-handler-wrap-visible,
.vort-input-number:hover .vort-input-number-handler-wrap,
.vort-input-number:focus-within .vort-input-number-handler-wrap {
    opacity: 1;
}

/* ========================================
   控制按钮
   ======================================== */
.vort-input-number-handler {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    user-select: none;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    transition: all var(--vort-transition-colors, 0.1s);
}

.vort-input-number-handler-up {
    border-bottom: 1px solid var(--vort-border, #d9d9d9);
}

.vort-input-number-handler:hover:not(.vort-input-number-handler-disabled) {
    color: var(--vort-primary, #1456f0);
    background: var(--vort-primary-bg, #e8f0fe);
}

.vort-input-number-handler-disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.vort-input-number-handler-icon {
    font-size: 10px;
}

/* ========================================
   Addon - 外层容器
   ======================================== */
.vort-input-number-addon-wrapper {
    display: inline-flex;
    align-items: center;
    width: 100%;
}

/* ========================================
   Addon - 前置/后置标签
   ======================================== */
.vort-input-number-addon {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    background: rgba(0, 0, 0, 0.02);
    border: 1px solid var(--vort-border, #d9d9d9);
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
}

.vort-input-number-addon-before {
    border-right: none;
    border-radius: var(--vort-radius, 6px) 0 0 var(--vort-radius, 6px);
}

.vort-input-number-addon-after {
    border-left: none;
    border-radius: 0 var(--vort-radius, 6px) var(--vort-radius, 6px) 0;
}

/* Addon 尺寸 */
.vort-input-number-addon-large {
    height: var(--vort-height-lg, 40px);
    padding: 0 11px;
    font-size: var(--vort-font-size-md, 16px);
}

.vort-input-number-addon-middle {
    height: var(--vort-height-md, 32px);
    padding: 0 11px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-input-number-addon-small {
    height: var(--vort-height-sm, 24px);
    padding: 0 7px;
    font-size: var(--vort-font-size-sm, 14px);
}

/* ========================================
   Addon - Compact 模式（适合放 Select 等组件）
   ======================================== */
.vort-input-number-addon-compact {
    padding: 0;
    background: rgba(0, 0, 0, 0.02);
    overflow: hidden;
    position: relative;
    transition: var(--vort-transition-colors, border-color 0.1s);
}

.vort-input-number-addon-compact:hover {
    border-color: var(--vort-primary, #1456f0);
    z-index: 1;
}

.vort-input-number-addon-compact:focus-within {
    border-color: var(--vort-primary, #1456f0);
    z-index: 1;
}

/* Compact 模式下子元素背景透明 */
.vort-input-number-addon-compact > :deep(*) {
    background: transparent !important;
}

/* ========================================
   有 Addon 时调整 Wrapper 圆角
   ======================================== */
.vort-input-number-has-addon-before {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}

.vort-input-number-has-addon-after {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}

.vort-input-number-has-addon-before.vort-input-number-has-addon-after {
    border-radius: 0;
}

/* ========================================
   Compact 模式下的边框重叠
   ======================================== */
.vort-input-number-compact.vort-input-number-has-addon-before {
    margin-left: -1px;
}

.vort-input-number-compact:hover,
.vort-input-number-compact:focus-within {
    position: relative;
    z-index: 1;
}

.vort-input-number-addon-compact.vort-input-number-addon-after {
    margin-left: -1px;
}
</style>

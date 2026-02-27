<script setup lang="ts">
import { computed, ref, useAttrs, watch, nextTick, onMounted } from "vue";
import type { StyleValue } from "vue";
import { CloseCircleFilled } from "@/components/vort/icons";

defineOptions({ name: "VortTextarea", inheritAttrs: false });

/** Vort Textarea - 多行文本输入框组件 */

type TextareaSize = "large" | "middle" | "small";
type TextareaStatus = "error" | "warning";

interface AutoSizeType {
    minRows?: number;
    maxRows?: number;
}

interface Props {
    /** 输入框内容（v-model） */
    modelValue?: string;
    /** 默认值（非受控模式） */
    defaultValue?: string;
    /** 尺寸 */
    size?: TextareaSize;
    /** 输入框状态 */
    status?: TextareaStatus;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否有边框 */
    bordered?: boolean;
    /** 输入框占位文本 */
    placeholder?: string;
    /** 自定义类名 */
    class?: string;
    /** 可以点击清除图标删除内容 */
    allowClear?: boolean;
    /** 最大输入长度 */
    maxlength?: number;
    /** 是否展示字数 */
    showCount?: boolean;
    /** 固定行数 */
    rows?: number;
    /** 自适应内容高度，可设置为 true 或对象 { minRows: 2, maxRows: 6 } */
    autoSize?: boolean | AutoSizeType;
}

const props = withDefaults(defineProps<Props>(), {
    size: "middle",
    disabled: false,
    bordered: true,
    allowClear: false,
    showCount: false,
    rows: 4
});

const emit = defineEmits<{
    "update:modelValue": [value: string];
    change: [event: Event];
    input: [event: Event];
    focus: [event: FocusEvent];
    blur: [event: FocusEvent];
    pressEnter: [event: KeyboardEvent];
    clear: [];
}>();

const attrs = useAttrs();
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const isFocused = ref(false);
const attrsStyle = computed<StyleValue | undefined>(() => attrs.style as StyleValue | undefined);

// 内部值
const innerValue = ref<string>(String(props.modelValue ?? props.defaultValue ?? ""));

// 监听 modelValue 变化
watch(
    () => props.modelValue,
    (newVal) => {
        if (newVal !== undefined) {
            innerValue.value = String(newVal ?? "");
        }
    }
);

// 自动调整高度
const adjustHeight = async () => {
    if (!props.autoSize || !textareaRef.value) return;

    await nextTick();
    const textarea = textareaRef.value;

    // 重置高度以便正确计算
    textarea.style.height = "auto";

    const computedStyle = window.getComputedStyle(textarea);
    const lineHeight = parseFloat(computedStyle.lineHeight) || 22;
    const paddingTop = parseFloat(computedStyle.paddingTop) || 0;
    const paddingBottom = parseFloat(computedStyle.paddingBottom) || 0;
    const borderTop = parseFloat(computedStyle.borderTopWidth) || 0;
    const borderBottom = parseFloat(computedStyle.borderBottomWidth) || 0;

    // 计算内容高度
    const scrollHeight = textarea.scrollHeight;

    // 计算最小/最大高度
    let minHeight = 0;
    let maxHeight = Infinity;

    if (typeof props.autoSize === "object") {
        const { minRows, maxRows } = props.autoSize;
        if (minRows) {
            minHeight = minRows * lineHeight + paddingTop + paddingBottom + borderTop + borderBottom;
        }
        if (maxRows) {
            maxHeight = maxRows * lineHeight + paddingTop + paddingBottom + borderTop + borderBottom;
        }
    }

    // 应用高度
    const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
    textarea.style.height = `${newHeight}px`;
};

// 监听值变化，调整高度
watch(innerValue, () => {
    adjustHeight();
});

// 初始化时调整高度
onMounted(() => {
    adjustHeight();
});

// 是否应该渲染清除按钮
const shouldRenderClearButton = computed(() => props.allowClear && !props.disabled);

// 清除按钮是否可见（有内容时显示）
const isClearButtonVisible = computed(() => shouldRenderClearButton.value && !!innerValue.value);

// 是否显示底部区域（清除按钮或字数统计）
const hasFooter = computed(() => props.allowClear || props.showCount);

// 字数统计文本
const countText = computed(() => {
    const len = innerValue.value.length;
    if (props.maxlength !== undefined) {
        return `${len} / ${props.maxlength}`;
    }
    return String(len);
});

// ========== 类名计算（只负责切换状态类名）==========

/** Wrapper 类名 */
const wrapperClasses = computed(() => {
    const classes = ["vort-textarea-wrapper", `vort-textarea-${props.size}`];
    if (props.status) classes.push(`vort-textarea-${props.status}`);
    if (props.disabled) classes.push("vort-textarea-disabled");
    if (!props.bordered) classes.push("vort-textarea-borderless");
    if (props.class) classes.push(props.class);
    return classes;
});

/** 纯 Textarea 类名（无 wrapper 时使用） */
const textareaOnlyClasses = computed(() => {
    const classes = ["vort-textarea", `vort-textarea-${props.size}`];
    if (props.status) classes.push(`vort-textarea-${props.status}`);
    if (props.disabled) classes.push("vort-textarea-disabled");
    if (!props.bordered) classes.push("vort-textarea-borderless");
    if (props.class) classes.push(props.class);
    return classes;
});

// ========== 事件处理 ==========

const handleInput = (event: Event) => {
    const target = event.target as HTMLTextAreaElement;
    innerValue.value = target.value;
    emit("update:modelValue", target.value);
    emit("input", event);
};

const handleChange = (event: Event) => {
    emit("change", event);
};

const handleFocus = (event: FocusEvent) => {
    isFocused.value = true;
    emit("focus", event);
};

const handleBlur = (event: FocusEvent) => {
    isFocused.value = false;
    emit("blur", event);
};

const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
        emit("pressEnter", event);
    }
};

const handleClear = () => {
    innerValue.value = "";
    emit("update:modelValue", "");
    emit("clear");
    textareaRef.value?.focus();
    adjustHeight();
};

const handleWrapperClick = () => {
    if (!props.disabled) {
        textareaRef.value?.focus();
    }
};

// 暴露方法
defineExpose({
    textarea: textareaRef,
    focus: () => textareaRef.value?.focus(),
    blur: () => textareaRef.value?.blur(),
    resizeTextarea: adjustHeight
});
</script>

<template>
    <!-- 有底部区域时使用 wrapper -->
    <span v-if="hasFooter" :class="wrapperClasses" :style="attrsStyle" @click="handleWrapperClick">
        <!-- 文本域 -->
        <textarea
            ref="textareaRef"
            :value="innerValue"
            class="vort-textarea-inner"
            :disabled="disabled"
            :placeholder="placeholder"
            :maxlength="maxlength"
            :rows="autoSize ? undefined : rows"
            @input="handleInput"
            @change="handleChange"
            @focus="handleFocus"
            @blur="handleBlur"
            @keydown="handleKeydown"
        />

        <!-- 底部区域（清除按钮、字数统计） -->
        <span class="vort-textarea-footer">
            <!-- 清除按钮 -->
            <span
                v-if="shouldRenderClearButton"
                class="vort-textarea-clear"
                :class="{ 'vort-textarea-clear-visible': isClearButtonVisible }"
                role="button"
                tabindex="-1"
                @click="handleClear"
                @mousedown.prevent
            >
                <CloseCircleFilled />
            </span>

            <!-- 字数统计 -->
            <span v-if="showCount" class="vort-textarea-count">
                {{ countText }}
            </span>
        </span>
    </span>

    <!-- 无底部区域时直接渲染 textarea -->
    <textarea
        v-else
        ref="textareaRef"
        :value="innerValue"
        :class="textareaOnlyClasses"
        :style="attrsStyle"
        :disabled="disabled"
        :placeholder="placeholder"
        :maxlength="maxlength"
        :rows="autoSize ? undefined : rows"
        @input="handleInput"
        @change="handleChange"
        @focus="handleFocus"
        @blur="handleBlur"
        @keydown="handleKeydown"
    />
</template>

<style scoped>
/* ========================================
   CSS Variables（局部变量，可被状态类覆盖）
   ======================================== */

/* ========================================
   基础样式 - Wrapper
   ======================================== */
.vort-textarea-wrapper {
    /* 局部变量 - 可被状态类覆盖 */
    --_border-color: var(--vort-border, #d9d9d9);
    --_focus-color: var(--vort-primary, #1456f0);
    --_focus-shadow: var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
    --_bg-color: #fff;

    display: inline-flex;
    flex-direction: column;
    width: 100%;
    border: 1px solid var(--_border-color);
    border-radius: var(--vort-radius, 6px);
    background: var(--_bg-color);
    cursor: text;
    transition: var(--vort-transition-all, all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1));
}

/* ========================================
   基础样式 - 纯 Textarea（无 wrapper）
   ======================================== */
.vort-textarea {
    --_border-color: var(--vort-border, #d9d9d9);
    --_focus-color: var(--vort-primary, #1456f0);
    --_focus-shadow: var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
    --_bg-color: #fff;

    width: 100%;
    border: 1px solid var(--_border-color);
    border-radius: var(--vort-radius, 6px);
    background: var(--_bg-color);
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    outline: none;
    resize: none;
    transition: var(--vort-transition-all, all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1));
}

.vort-textarea::placeholder {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   交互状态 - Hover
   ======================================== */
.vort-textarea-wrapper:hover:not(.vort-textarea-disabled) {
    border-color: var(--_focus-color);
}

.vort-textarea:hover:not(.vort-textarea-disabled) {
    border-color: var(--_focus-color);
}

/* ========================================
   交互状态 - Focus
   ======================================== */
.vort-textarea-wrapper:focus-within:not(.vort-textarea-disabled) {
    border-color: var(--_focus-color);
    box-shadow: 0 0 0 2px var(--_focus-shadow);
}

.vort-textarea:focus:not(.vort-textarea-disabled) {
    border-color: var(--_focus-color);
    box-shadow: 0 0 0 2px var(--_focus-shadow);
}

/* ========================================
   状态覆盖 - Error
   ======================================== */
.vort-textarea-error {
    --_border-color: var(--vort-error, #ff4d4f);
    --_focus-color: var(--vort-error, #ff4d4f);
    --_focus-shadow: rgba(255, 77, 79, 0.06);
}

/* ========================================
   状态覆盖 - Warning
   ======================================== */
.vort-textarea-warning {
    --_border-color: var(--vort-warning, #faad14);
    --_focus-color: var(--vort-warning, #faad14);
    --_focus-shadow: rgba(250, 173, 20, 0.1);
}

/* ========================================
   状态覆盖 - Disabled
   ======================================== */
.vort-textarea-disabled {
    --_bg-color: rgba(0, 0, 0, 0.04);
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: not-allowed;
}

.vort-textarea-disabled .vort-textarea-inner {
    cursor: not-allowed;
}

/* ========================================
   状态覆盖 - Borderless
   ======================================== */
.vort-textarea-borderless {
    border-color: transparent;
    background: transparent;
}

.vort-textarea-borderless:hover:not(.vort-textarea-disabled),
.vort-textarea-borderless:focus-within:not(.vort-textarea-disabled),
.vort-textarea.vort-textarea-borderless:focus:not(.vort-textarea-disabled) {
    border-color: transparent;
    box-shadow: none;
}

/* ========================================
   尺寸 - Large
   ======================================== */
.vort-textarea-large {
    font-size: var(--vort-font-size-md, 16px);
}

.vort-textarea-large .vort-textarea-inner,
.vort-textarea.vort-textarea-large {
    padding: 6.5px 11px;
}

.vort-textarea-large .vort-textarea-footer {
    padding: 0 11px 6.5px;
}

/* ========================================
   尺寸 - Middle（默认）
   ======================================== */
.vort-textarea-middle {
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-textarea-middle .vort-textarea-inner,
.vort-textarea.vort-textarea-middle {
    padding: 5px 11px;
}

.vort-textarea-middle .vort-textarea-footer {
    padding: 0 11px 5px;
}

/* ========================================
   尺寸 - Small
   ======================================== */
.vort-textarea-small {
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-textarea-small .vort-textarea-inner,
.vort-textarea.vort-textarea-small {
    padding: 5px 7px;
}

.vort-textarea-small .vort-textarea-footer {
    padding: 0 7px 5px;
}

/* ========================================
   内部元素 - Textarea Inner
   ======================================== */
.vort-textarea-inner {
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-textarea-inner::placeholder {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   底部区域
   ======================================== */
.vort-textarea-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   清除按钮
   ======================================== */
.vort-textarea-clear {
    display: flex;
    align-items: center;
    font-size: 14px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: pointer;
    visibility: hidden;
    transition: color var(--vort-transition-colors, 0.1s);
}

.vort-textarea-clear-visible {
    visibility: visible;
}

.vort-textarea-clear:hover {
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
}

/* ========================================
   字数统计
   ======================================== */
.vort-textarea-count {
    font-size: 12px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    white-space: nowrap;
}
</style>

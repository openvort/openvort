<script setup lang="ts">
import { computed, ref, useAttrs } from "vue";
import VortInput from "./Input.vue";
import VortButton from "@/components/vort/button/Button.vue";
import { SearchOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortInputSearch", inheritAttrs: false });

/** Vort InputSearch - 搜索输入框组件 */

type InputSize = "large" | "middle" | "small";
type InputStatus = "error" | "warning";
type InputVariant = "outlined" | "filled" | "borderless" | "underlined";

interface Props {
    /** 输入框内容（v-model） */
    modelValue?: string;
    /** 默认值（非受控模式） */
    defaultValue?: string;
    /** 尺寸 */
    size?: InputSize;
    /** 输入框状态 */
    status?: InputStatus;
    /** 输入框形态变体 */
    variant?: InputVariant;
    /** 是否禁用 */
    disabled?: boolean;
    /** 输入框占位文本 */
    placeholder?: string;
    /** 自定义类名 */
    class?: string;
    /** 是否有确认按钮（可设为按钮文字），true 为蓝色按钮，false 为白色按钮 */
    enterButton?: boolean | string;
    /** 搜索按钮加载状态 */
    loading?: boolean;
    /** 是否可清除 */
    allowClear?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    size: "middle",
    disabled: false,
    enterButton: false,
    loading: false,
    allowClear: false,
    variant: "outlined"
});

const emit = defineEmits<{
    "update:modelValue": [value: string];
    change: [event: Event];
    input: [event: Event];
    focus: [event: FocusEvent];
    blur: [event: FocusEvent];
    search: [value: string, event?: MouseEvent | KeyboardEvent];
    clear: [];
}>();

const attrs = useAttrs();
const inputRef = ref<InstanceType<typeof VortInput> | null>(null);

// 内部值
const innerValue = computed(() => String(props.modelValue ?? props.defaultValue ?? ""));

// 是否使用 primary 样式按钮
const isPrimaryButton = computed(() => props.enterButton === true || typeof props.enterButton === "string");

// 搜索按钮文本
const enterButtonText = computed(() => {
    if (typeof props.enterButton === "string") {
        return props.enterButton;
    }
    return "";
});

// 透传给 Input 的 props
const inputProps = computed(() => ({
    modelValue: props.modelValue,
    defaultValue: props.defaultValue,
    size: props.size,
    status: props.status,
    variant: props.variant,
    disabled: props.disabled,
    placeholder: props.placeholder,
    allowClear: props.allowClear,
    addonButtonMode: true // 使用按钮模式的 addon
}));

// ========== 类名计算 ==========

/** 外层容器类名 */
const wrapperClasses = computed(() => {
    const classes = ["vort-input-search"];
    if (isPrimaryButton.value) classes.push("vort-input-search--primary");
    if (props.class) classes.push(props.class);
    return classes.join(" ");
});

/** Button 类名 */
const buttonClasses = computed(() => {
    const classes = ["vort-input-search-button"];
    if (props.variant === "underlined") {
        classes.push("vort-input-search-button-underlined");
        if (!isPrimaryButton.value) classes.push("vort-input-search-button-underlined-default");
    }
    return classes.join(" ");
});

// ========== 事件处理 ==========

const handleModelValueUpdate = (val: string) => {
    emit("update:modelValue", val);
};

const handleInput = (event: Event) => {
    emit("input", event);
};

const handleChange = (event: Event) => {
    emit("change", event);
};

const handleFocus = (event: FocusEvent) => {
    emit("focus", event);
};

const handleBlur = (event: FocusEvent) => {
    emit("blur", event);
};

const handleClear = () => {
    emit("clear");
};

const handleSearch = (event?: MouseEvent | KeyboardEvent) => {
    if (!props.disabled && !props.loading) {
        emit("search", innerValue.value, event);
    }
};

const handleKeydownEnter = (event: KeyboardEvent) => {
    handleSearch(event);
};

// 暴露方法
defineExpose({
    /** 获取输入框元素 */
    input: computed(() => inputRef.value?.input),
    /** 聚焦输入框 */
    focus: () => inputRef.value?.focus(),
    /** 失焦输入框 */
    blur: () => inputRef.value?.blur()
});
</script>

<template>
    <span :class="wrapperClasses">
        <VortInput
            ref="inputRef"
            v-bind="{ ...inputProps, ...attrs }"
            class="vort-input-search-input"
            @update:model-value="handleModelValueUpdate"
            @input="handleInput"
            @change="handleChange"
            @focus="handleFocus"
            @blur="handleBlur"
            @clear="handleClear"
            @press-enter="handleKeydownEnter"
        >
            <!-- 透传 prefix slot -->
            <template v-if="$slots.prefix" #prefix>
                <slot name="prefix" />
            </template>

            <!-- 搜索按钮放在 addonAfter -->
            <template #addonAfter>
                <VortButton
                    :type="isPrimaryButton ? 'primary' : 'default'"
                    :size="size"
                    :disabled="disabled"
                    :loading="loading"
                    :class="buttonClasses"
                    @click="handleSearch"
                >
                    <SearchOutlined v-if="!enterButtonText" />
                    <template v-else>{{ enterButtonText }}</template>
                </VortButton>
            </template>
        </VortInput>
    </span>
</template>

<style scoped>
/* ========================================
   InputSearch 外层容器
   ======================================== */
.vort-input-search {
    display: inline-flex;
    width: 100%;
}

/* ========================================
   Input 部分样式
   参考 Ant Design Compact 组件的边框处理策略：
   - 使用负 margin 让边框重叠
   - hover/focus 时提升 z-index 让边框显示在上层
   ======================================== */
.vort-input-search :deep(.vort-input-wrapper),
.vort-input-search :deep(.vort-input) {
    border-top-right-radius: 0 !important;
    border-bottom-right-radius: 0 !important;
    /* Avoid overflow: input area should shrink with addon button */
    flex: 1 1 auto;
    width: auto !important;
    min-width: 0;
}

/* VortInput 外层容器 */
.vort-input-search :deep(.vort-input-addon-wrapper) {
    flex: 1;
    min-width: 0;
}

/* Input hover/focus 时提升 z-index，让边框显示在按钮上方 */
/* 需要同时处理 wrapper 模式和直接 input 模式 */
.vort-input-search :deep(.vort-input-wrapper),
.vort-input-search :deep(.vort-input) {
    position: relative;
    /* 默认让 input 在上层，避免 hover 时层级翻转产生闪烁 */
    z-index: 2;
}

/* 仅在 focus 时提升到最上层，保证 box-shadow 完整显示 */
.vort-input-search :deep(.vort-input-wrapper:focus-within),
.vort-input-search :deep(.vort-input:focus) {
    z-index: 3;
}

/* ========================================
   搜索按钮样式
   ======================================== */
.vort-input-search-button {
    border-top-left-radius: 0 !important;
    border-bottom-left-radius: 0 !important;
    margin-left: -1px;
    position: relative;
    z-index: 1;
}

/* Primary 搜索按钮：按钮常态在 input 上方，避免接缝露出灰边 */
.vort-input-search--primary :deep(.vort-input-wrapper),
.vort-input-search--primary :deep(.vort-input) {
    z-index: 1;
}

.vort-input-search--primary .vort-input-search-button {
    z-index: 2;
}

/* 按钮 hover/active 时提升 z-index 到更高层级 */
.vort-input-search-button:hover,
.vort-input-search-button:active {
    z-index: 3;
}

/* ========================================
   Underlined 变体按钮特殊处理
   ======================================== */
.vort-input-search-button-underlined {
    border-radius: 0 !important;
}

/* underlined + default 按钮：底部线条对齐 */
.vort-input-search-button-underlined-default {
    border: none !important;
    border-bottom: 1px solid var(--vort-border, #d9d9d9) !important;
    background: transparent !important;
}

.vort-input-search-button-underlined-default:hover:not(:disabled) {
    border-bottom-color: var(--vort-primary, #1456f0) !important;
    background: transparent !important;
}
</style>

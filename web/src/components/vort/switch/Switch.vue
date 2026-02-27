<script setup lang="ts">
import { computed, ref, useAttrs } from "vue";
import { LoadingOutlined } from "@/components/vort/icons";
import type { SwitchSize, SwitchValue } from "./types";

defineOptions({ name: "VortSwitch", inheritAttrs: false });

/** Vort Switch - 开关组件 */

interface Props {
    /** 指定当前值（v-model:checked），支持 boolean / number / string */
    checked?: SwitchValue;
    /** 是否禁用 */
    disabled?: boolean;
    /** 加载中 */
    loading?: boolean;
    /** 开关大小 */
    size?: SwitchSize;
    /** 选中时的内容 */
    checkedChildren?: string;
    /** 非选中时的内容（模板写法：un-checked-children） */
    unCheckedChildren?: string;
    /** 自定义类名 */
    class?: string;
    /** 切换前的钩子，返回 false 或 Promise reject 会阻止切换 */
    beforeChange?: () => Promise<boolean> | boolean;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false,
    loading: false,
    size: "default"
});

const emit = defineEmits<{
    "update:checked": [value: SwitchValue];
    change: [value: SwitchValue, event: MouseEvent];
}>();

// ==================== 内部状态 ====================

const isLoading = ref(false);

// ==================== 值映射（通过 $attrs 读取，避免 prop 名称冲突） ====================

const attrs = useAttrs();

/**
 * 值映射支持：通过 $attrs 获取 checkedValue / uncheckedValue
 * 不放入 Props 接口，避免与 checked 产生 Vue prop 归一化冲突
 *
 * 支持的模板写法：
 *   :checked-value="1"       → attrs.checkedValue
 *   :un-checked-value="0"    → attrs.unCheckedValue
 *   :unchecked-value="0"     → attrs.uncheckedValue
 */
const checkedValueAttr = computed<SwitchValue | undefined>(() => attrs.checkedValue as SwitchValue | undefined);
const uncheckedValueAttr = computed<SwitchValue | undefined>(() => (attrs.unCheckedValue ?? attrs.uncheckedValue) as SwitchValue | undefined);
const useValueMapping = computed(() => checkedValueAttr.value !== undefined || uncheckedValueAttr.value !== undefined);
const resolvedCheckedValue = computed<SwitchValue>(() => checkedValueAttr.value ?? true);
const resolvedUncheckedValue = computed<SwitchValue>(() => uncheckedValueAttr.value ?? false);

// ==================== 计算属性 ====================

/** 当前是否选中 */
const isChecked = computed(() => {
    if (useValueMapping.value) {
        return props.checked === resolvedCheckedValue.value;
    }
    return Boolean(props.checked);
});

/** 是否实际禁用（禁用或加载中都不可点击） */
const isActuallyDisabled = computed(() => props.disabled || props.loading || isLoading.value);

/** 实际显示的加载状态 */
const showLoading = computed(() => props.loading || isLoading.value);

// ==================== 类名计算 ====================

const switchClasses = computed(() => {
    const classes = ["vort-switch"];
    if (isChecked.value) classes.push("vort-switch-checked");
    if (isActuallyDisabled.value) classes.push("vort-switch-disabled");
    if (props.size === "small") classes.push("vort-switch-small");
    if (props.class) classes.push(props.class);
    return classes;
});

// ==================== 方法 ====================

/** 计算切换后的新值 */
const getNewValue = (): SwitchValue => {
    const newChecked = !isChecked.value;
    if (useValueMapping.value) {
        return newChecked ? resolvedCheckedValue.value : resolvedUncheckedValue.value;
    }
    return newChecked;
};

/** 执行切换 */
const doSwitch = async (event: MouseEvent | KeyboardEvent): Promise<void> => {
    if (props.beforeChange) {
        isLoading.value = true;
        try {
            const result = await props.beforeChange();
            if (result) {
                const newVal = getNewValue();
                emit("update:checked", newVal);
                emit("change", newVal, event as MouseEvent);
            }
        } catch {
            // 失败时不切换
        } finally {
            isLoading.value = false;
        }
    } else {
        const newVal = getNewValue();
        emit("update:checked", newVal);
        emit("change", newVal, event as MouseEvent);
    }
};

/** 处理点击 */
const handleClick = (event: MouseEvent) => {
    if (isActuallyDisabled.value) return;
    doSwitch(event);
};

/** 处理键盘事件 */
const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (!isActuallyDisabled.value) {
            doSwitch(event);
        }
    }
};

/** 过滤掉值映射相关的 attrs，其余透传到根元素 */
const VALUE_MAPPING_KEYS = new Set(["checkedValue", "checked-value", "unCheckedValue", "un-checked-value", "uncheckedValue", "unchecked-value"]);
const filteredAttrs = computed(() => {
    const result: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(attrs)) {
        if (!VALUE_MAPPING_KEYS.has(key)) {
            result[key] = val;
        }
    }
    return result;
});
</script>

<template>
    <button
        type="button"
        role="switch"
        v-bind="filteredAttrs"
        :aria-checked="isChecked"
        :aria-disabled="isActuallyDisabled"
        :class="switchClasses"
        :disabled="isActuallyDisabled"
        @click="handleClick"
        @keydown="handleKeydown"
    >
        <!-- 滑块 -->
        <span class="vort-switch-handle">
            <LoadingOutlined v-if="showLoading" class="vort-switch-loading" />
        </span>

        <!-- 内容区域 -->
        <span class="vort-switch-inner">
            <span class="vort-switch-inner-checked">
                <slot name="checkedChildren">{{ checkedChildren }}</slot>
            </span>
            <span class="vort-switch-inner-unchecked">
                <slot name="unCheckedChildren">{{ unCheckedChildren }}</slot>
            </span>
        </span>
    </button>
</template>

<style scoped>
/* ========================================
   基础样式 - 开关容器
   ======================================== */
.vort-switch {
    --_bg-color: rgba(0, 0, 0, 0.25);
    --_bg-hover: rgba(0, 0, 0, 0.45);

    position: relative;
    display: inline-flex;
    align-items: center;
    box-sizing: border-box;
    min-width: 44px;
    height: 22px;
    padding: 0;
    background-color: var(--_bg-color);
    border: 0;
    border-radius: 100px;
    cursor: pointer;
    user-select: none;
    outline: none;
    transition: background-color var(--vort-duration-normal, 200ms) var(--vort-ease-in-out, cubic-bezier(0.645, 0.045, 0.355, 1));
}

/* Hover */
.vort-switch:hover:not(.vort-switch-disabled) {
    background-color: var(--_bg-hover);
}

/* ========================================
   状态覆盖 - 选中
   ======================================== */
.vort-switch-checked {
    --_bg-color: var(--vort-primary, #1456f0);
    --_bg-hover: var(--vort-primary-hover, #4078f2);
}

/* ========================================
   状态覆盖 - 禁用
   ======================================== */
.vort-switch-disabled {
    opacity: 0.65;
    cursor: not-allowed;
}

/* ========================================
   聚焦状态
   ======================================== */
.vort-switch:focus-visible {
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

/* ========================================
   滑块
   ======================================== */
.vort-switch-handle {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    background-color: #fff;
    border-radius: 50%;
    box-shadow: 0 2px 4px 0 rgba(0, 35, 11, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1;
    transition: left var(--vort-duration-normal, 200ms) var(--vort-ease-in-out, cubic-bezier(0.645, 0.045, 0.355, 1));
}

.vort-switch-checked .vort-switch-handle {
    left: calc(100% - 20px);
}

/* ========================================
   加载图标
   ======================================== */
.vort-switch-loading {
    width: 12px;
    height: 12px;
    color: var(--vort-primary, #1456f0);
    animation: vort-spin 1s linear infinite;
}

/* ========================================
   内容区域
   ======================================== */
.vort-switch-inner {
    display: flex;
    align-items: center;
    height: 100%;
    overflow: hidden;
    border-radius: 100px;
    padding-left: 24px;
    padding-right: 8px;
    transition: padding var(--vort-duration-normal, 200ms) var(--vort-ease-in-out, cubic-bezier(0.645, 0.045, 0.355, 1));
}

.vort-switch-checked .vort-switch-inner {
    padding-left: 8px;
    padding-right: 24px;
}

/* ========================================
   内容文字
   ======================================== */
.vort-switch-inner-checked,
.vort-switch-inner-unchecked {
    font-size: var(--vort-font-size-xs, 12px);
    line-height: 1;
    color: #fff;
    white-space: nowrap;
    pointer-events: none;
}

/* 未选中：隐藏 checked，显示 unchecked */
.vort-switch-inner-checked {
    display: none;
}

.vort-switch-inner-unchecked {
    display: block;
}

/* 选中：显示 checked，隐藏 unchecked */
.vort-switch-checked .vort-switch-inner-checked {
    display: block;
}

.vort-switch-checked .vort-switch-inner-unchecked {
    display: none;
}

/* ========================================
   尺寸 - Small
   ======================================== */
.vort-switch-small {
    min-width: 28px;
    height: 16px;
}

.vort-switch-small .vort-switch-handle {
    width: 12px;
    height: 12px;
}

.vort-switch-small.vort-switch-checked .vort-switch-handle {
    left: calc(100% - 14px);
}

.vort-switch-small .vort-switch-inner {
    padding-left: 16px;
    padding-right: 6px;
}

.vort-switch-small.vort-switch-checked .vort-switch-inner {
    padding-left: 6px;
    padding-right: 16px;
}

.vort-switch-small .vort-switch-inner-checked,
.vort-switch-small .vort-switch-inner-unchecked {
    font-size: 10px;
}

.vort-switch-small .vort-switch-loading {
    width: 8px;
    height: 8px;
}
</style>

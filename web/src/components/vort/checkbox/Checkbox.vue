<script setup lang="ts">
import { computed, inject, type Ref } from "vue";

defineOptions({ name: "VortCheckbox" });

/** Vort Checkbox - 复选框组件 */

interface Props {
    /** 复选框的值（在 CheckboxGroup 中使用） */
    value?: string | number;
    /** 是否选中（v-model:checked） */
    checked?: boolean;
    /** 设置 indeterminate 状态，只负责样式控制 */
    indeterminate?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false,
    indeterminate: false
});

const emit = defineEmits<{
    "update:checked": [checked: boolean];
    change: [event: Event, checked: boolean];
}>();

// 从 CheckboxGroup 注入上下文
interface CheckboxGroupContext {
    name: Ref<string | undefined>;
    disabled: Ref<boolean>;
    value: Ref<(string | number)[]>;
    onChange: (value: string | number, checked: boolean, event: Event) => void;
}

const checkboxGroupContext = inject<CheckboxGroupContext | null>("checkboxGroupContext", null);

// 是否被选中
const isChecked = computed(() => {
    if (checkboxGroupContext && props.value !== undefined) {
        return checkboxGroupContext.value.value.includes(props.value);
    }
    return props.checked;
});

// 是否禁用
const isDisabled = computed(() => {
    if (checkboxGroupContext) {
        return checkboxGroupContext.disabled.value || props.disabled;
    }
    return props.disabled;
});

// 处理点击
const handleChange = (event: Event) => {
    if (isDisabled.value) return;

    const newChecked = !isChecked.value;

    if (checkboxGroupContext && props.value !== undefined) {
        checkboxGroupContext.onChange(props.value, newChecked, event);
    } else {
        emit("update:checked", newChecked);
        emit("change", event, newChecked);
    }
};

// ========== 类名计算（只负责切换状态类名）==========

/** 容器类名 */
const wrapperClasses = computed(() => {
    const classes = ["vort-checkbox"];
    if (isDisabled.value) classes.push("vort-checkbox-disabled");
    if (props.class) classes.push(props.class);
    return classes;
});

/** 选择框类名 */
const checkboxInnerClasses = computed(() => {
    const classes = ["vort-checkbox-inner"];
    if (isChecked.value) classes.push("vort-checkbox-checked");
    if (props.indeterminate && !isChecked.value) classes.push("vort-checkbox-indeterminate");
    if (isDisabled.value) classes.push("vort-checkbox-inner-disabled");
    return classes;
});
</script>

<template>
    <label :class="wrapperClasses">
        <input
            type="checkbox"
            class="vort-checkbox-input"
            :name="checkboxGroupContext?.name.value"
            :value="value"
            :checked="isChecked"
            :disabled="isDisabled"
            @change="handleChange"
        />
        <span :class="checkboxInnerClasses">
            <!-- 半选标记 -->
            <span v-if="indeterminate && !isChecked" class="vort-checkbox-indeterminate-mark" />
            <!-- 勾选标记用 CSS ::after 伪元素实现，自带弹性动画 -->
        </span>
        <span v-if="$slots.default" class="vort-checkbox-label">
            <slot />
        </span>
    </label>
</template>

<style scoped>
/* ========================================
   CSS Variables（局部变量，可被状态类覆盖）
   ======================================== */

/* ========================================
   基础样式 - 容器
   ======================================== */
.vort-checkbox {
    display: inline-flex;
    align-items: center;
    min-height: 32px;
    cursor: pointer;
    user-select: none;
}

.vort-checkbox-disabled {
    cursor: not-allowed;
}

/* ========================================
   隐藏的原生 input
   ======================================== */
.vort-checkbox-input {
    position: absolute;
    width: 0;
    height: 0;
    opacity: 0;
}

/* ========================================
   选择框外框
   ======================================== */
.vort-checkbox-inner {
    position: relative;
    display: inline-block;
    flex-shrink: 0;
    width: 16px;
    height: 16px;
    border: 1px solid var(--vort-border, #d9d9d9);
    border-radius: var(--vort-radius-sm, 4px);
    background: #fff;
    transition: all var(--vort-duration-normal, 200ms) var(--vort-ease-in-out, cubic-bezier(0.645, 0.045, 0.355, 1));
}

/* Hover 状态 */
.vort-checkbox:not(.vort-checkbox-disabled) .vort-checkbox-inner:not(.vort-checkbox-checked):not(.vort-checkbox-indeterminate):hover {
    border-color: var(--vort-primary, #1456f0);
}

/* ========================================
   勾选标记 - 使用 ::after 伪元素实现弹性动画
   ======================================== */
.vort-checkbox-inner::after {
    box-sizing: border-box;
    position: absolute;
    top: 50%;
    inset-inline-start: 21.5%;
    display: table;
    width: 5.71px;
    height: 9.14px;
    border: 2px solid #fff;
    border-top: 0;
    border-inline-start: 0;
    transform: rotate(45deg) scale(0) translate(-50%, -50%);
    opacity: 0;
    content: "";
    transition:
        all var(--vort-duration-fast, 100ms) cubic-bezier(0.71, -0.46, 0.88, 0.6),
        opacity var(--vort-duration-fast, 100ms);
}

/* 选中时勾选标记弹性放大 */
.vort-checkbox-checked::after {
    opacity: 1;
    transform: rotate(45deg) scale(1) translate(-50%, -50%);
    transition: all var(--vort-duration-normal, 200ms) cubic-bezier(0.12, 0.4, 0.29, 1.46) var(--vort-duration-fast, 100ms);
}

/* ========================================
   半选标记
   ======================================== */
.vort-checkbox-indeterminate-mark {
    position: absolute;
    inset: 0;
    width: 8px;
    height: 8px;
    margin: auto;
    background-color: var(--vort-primary, #1456f0);
    border-radius: 1px;
}

/* ========================================
   状态覆盖 - 选中
   ======================================== */
.vort-checkbox-checked {
    border-color: var(--vort-primary, #1456f0);
    background: var(--vort-primary, #1456f0);
}

/* ========================================
   状态覆盖 - 半选
   ======================================== */
.vort-checkbox-indeterminate {
    border-color: var(--vort-primary, #1456f0);
    background: #fff;
}

/* ========================================
   状态覆盖 - 禁用
   ======================================== */
.vort-checkbox-inner-disabled {
    border-color: var(--vort-border, #d9d9d9);
    background: rgba(0, 0, 0, 0.04);
    cursor: not-allowed;
}

.vort-checkbox-inner-disabled.vort-checkbox-checked {
    border-color: var(--vort-border, #d9d9d9);
    background: rgba(0, 0, 0, 0.04);
}

.vort-checkbox-inner-disabled.vort-checkbox-checked::after {
    border-color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

.vort-checkbox-inner-disabled.vort-checkbox-indeterminate .vort-checkbox-indeterminate-mark {
    background-color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   标签文字
   ======================================== */
.vort-checkbox-label {
    margin-left: 8px;
    font-size: var(--vort-font-size-sm, 14px);
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-checkbox-disabled .vort-checkbox-label {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}
</style>

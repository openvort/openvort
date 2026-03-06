<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, getCurrentInstance, type Ref } from "vue";

defineOptions({ name: "VortRadioButton" });

/** Vort RadioButton - 单选按钮组件 */

interface Props {
    /** 单选框的值 */
    value?: string | number;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false
});

// 获取当前组件实例的 uid，用于注册机制
const instance = getCurrentInstance();
const uid = instance?.uid ?? Math.random();

// 从 RadioGroup 注入上下文
interface RadioGroupContext {
    name: Ref<string | undefined>;
    disabled: Ref<boolean>;
    size: Ref<"large" | "middle" | "small">;
    buttonStyle: Ref<"outline" | "solid" | "plain">;
    value: Ref<string | number | undefined>;
    onChange: (value: string | number, event: Event) => void;
    // 注册机制
    registerButton?: (uid: number) => void;
    unregisterButton?: (uid: number) => void;
    getButtonPosition?: (uid: number) => { isFirst: boolean; isLast: boolean };
    registeredButtons?: number[];
}

const radioGroupContext = inject<RadioGroupContext | null>("radioGroupContext", null);

// 注册/注销当前组件
onMounted(() => {
    radioGroupContext?.registerButton?.(uid);
});

onUnmounted(() => {
    radioGroupContext?.unregisterButton?.(uid);
});

// 获取当前按钮在组中的位置（响应式）
const position = computed(() => {
    // 访问 registeredButtons 以触发响应式更新
    // eslint-disable-next-line @typescript-eslint/no-unused-expressions
    radioGroupContext?.registeredButtons?.length;
    return radioGroupContext?.getButtonPosition?.(uid) ?? { isFirst: false, isLast: false };
});

// 是否被选中
const isChecked = computed(() => {
    if (radioGroupContext) {
        return radioGroupContext.value.value === props.value;
    }
    return false;
});

// 是否禁用
const isDisabled = computed(() => {
    if (radioGroupContext) {
        return radioGroupContext.disabled.value || props.disabled;
    }
    return props.disabled;
});

// 尺寸
const size = computed(() => {
    if (radioGroupContext) {
        return radioGroupContext.size.value;
    }
    return "middle";
});

// 按钮风格
const buttonStyle = computed(() => {
    if (radioGroupContext) {
        return radioGroupContext.buttonStyle.value;
    }
    return "outline";
});

// 处理点击
const handleChange = (event: Event) => {
    if (isDisabled.value) return;

    if (radioGroupContext && props.value !== undefined) {
        // 值没有变化时不触发，避免重复事件
        if (radioGroupContext.value.value === props.value) return;
        radioGroupContext.onChange(props.value, event);
    }
};

// 按钮样式
const buttonClasses = computed(() => {
    const { isFirst, isLast } = position.value;
    const classes = ["vort-radio-button"];

    // 尺寸
    classes.push(`vort-radio-button-${size.value}`);

    // 风格
    classes.push(`vort-radio-button-${buttonStyle.value}`);

    // plain 风格：每个按钮独立圆角，无边框合并
    if (buttonStyle.value === "plain") {
        classes.push("vort-radio-button-plain-rounded");
    } else {
        // 通过注册机制判断位置，而非 CSS first/last 伪类
        // 这样即使有 tooltip 等包装元素也能正确处理圆角
        if (isFirst) classes.push("vort-radio-button-first");
        if (isLast) classes.push("vort-radio-button-last");
        if (!isFirst) classes.push("vort-radio-button-not-first");
    }

    // 选中状态
    if (isChecked.value) classes.push("vort-radio-button-checked");

    // 禁用状态
    if (isDisabled.value) classes.push("vort-radio-button-disabled");

    if (props.class) classes.push(props.class);

    return classes;
});
</script>

<template>
    <label :class="buttonClasses">
        <input
            type="radio"
            class="vort-radio-button-input"
            :name="radioGroupContext?.name.value"
            :value="value"
            :checked="isChecked"
            :disabled="isDisabled"
            @click="handleChange"
        />
        <span>
            <slot />
        </span>
    </label>
</template>

<style scoped>
.vort-radio-button {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--vort-border);
    background: #fff;
    color: var(--vort-text);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    transition:
        color var(--vort-duration-normal, 200ms),
        background-color var(--vort-duration-normal, 200ms),
        box-shadow var(--vort-duration-normal, 200ms);
}

.vort-radio-button-input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
}

/* 尺寸 */
.vort-radio-button-large {
    height: 40px;
    padding: 0 16px;
    font-size: 16px;
}

.vort-radio-button-middle {
    height: 32px;
    padding: 0 16px;
    font-size: 14px;
}

.vort-radio-button-small {
    height: 24px;
    padding: 0 8px;
    font-size: 14px;
}

/* 位置 - 圆角处理 */
.vort-radio-button-first {
    border-top-left-radius: var(--vort-border-radius, 6px);
    border-bottom-left-radius: var(--vort-border-radius, 6px);
}

.vort-radio-button-last {
    border-top-right-radius: var(--vort-border-radius, 6px);
    border-bottom-right-radius: var(--vort-border-radius, 6px);
}

.vort-radio-button-not-first {
    margin-left: -1px;
}

/* Plain 风格独立圆角 */
.vort-radio-button-plain-rounded {
    border-radius: var(--vort-border-radius, 6px);
}

/* ==================== Outline 风格 ==================== */
.vort-radio-button-outline {
    border-color: var(--vort-border);
    background: #fff;
    color: var(--vort-text);
}

.vort-radio-button-outline:not(.vort-radio-button-disabled):hover {
    color: var(--vort-primary);
}

.vort-radio-button-outline.vort-radio-button-checked {
    border-color: var(--vort-primary);
    color: var(--vort-primary);
    z-index: 1;
}

/* ==================== Solid 风格 ==================== */
.vort-radio-button-solid {
    border-color: var(--vort-border);
    background: #fff;
    color: var(--vort-text);
}

.vort-radio-button-solid:not(.vort-radio-button-disabled):hover {
    color: var(--vort-primary);
}

.vort-radio-button-solid.vort-radio-button-checked {
    border-color: var(--vort-primary);
    background: var(--vort-primary);
    color: #fff;
    z-index: 1;
}

.vort-radio-button-solid.vort-radio-button-checked:not(.vort-radio-button-disabled):hover {
    color: #fff;
}

/* ==================== Plain 风格 ==================== */
.vort-radio-button-plain {
    border-color: transparent;
    background: transparent;
    color: var(--vort-text);
}

.vort-radio-button-plain:not(.vort-radio-button-disabled):hover {
    color: var(--vort-primary);
}

.vort-radio-button-plain.vort-radio-button-checked {
    border-color: var(--vort-primary);
    background: var(--vort-primary-bg);
    color: var(--vort-primary);
}

/* ==================== 禁用状态 ==================== */
.vort-radio-button-disabled {
    border-color: var(--vort-border);
    background: rgba(0, 0, 0, 0.04);
    color: rgba(0, 0, 0, 0.25);
    cursor: not-allowed;
}

/* Focus 样式 */
.vort-radio-button:focus-within {
    z-index: 1;
}

.vort-radio-button-disabled:focus-within {
    box-shadow: none;
}
</style>

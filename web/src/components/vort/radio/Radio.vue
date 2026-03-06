<script setup lang="ts">
import { computed, inject, type Ref } from "vue";

defineOptions({ name: "VortRadio" });

/** Vort Radio - 单选框组件 */

interface Props {
    /** 单选框的值 */
    value?: string | number;
    /** 是否选中（仅在非 RadioGroup 下使用） */
    checked?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false
});

const emit = defineEmits<{
    "update:checked": [checked: boolean];
    change: [event: Event];
}>();

// 从 RadioGroup 注入上下文
interface RadioGroupContext {
    name: Ref<string | undefined>;
    disabled: Ref<boolean>;
    size: Ref<"large" | "middle" | "small">;
    value: Ref<string | number | undefined>;
    onChange: (value: string | number, event: Event) => void;
}

const radioGroupContext = inject<RadioGroupContext | null>("radioGroupContext", null);

// 是否被选中
const isChecked = computed(() => {
    if (radioGroupContext) {
        return radioGroupContext.value.value === props.value;
    }
    return props.checked;
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

// 处理点击
const handleChange = (event: Event) => {
    if (isDisabled.value) return;

    if (radioGroupContext && props.value !== undefined) {
        radioGroupContext.onChange(props.value, event);
    } else {
        emit("update:checked", true);
        emit("change", event);
    }
};

// 尺寸配置
const sizeConfig = computed(() => {
    const config = {
        large: { size: 18 },
        middle: { size: 16 },
        small: { size: 14 }
    };
    return config[size.value];
});

// 单选框样式（直接使用像素值）
const radioStyles = computed(() => {
    const radioSize = sizeConfig.value.size;
    return {
        width: `${radioSize}px`,
        height: `${radioSize}px`
    };
});

// 内圆样式（直接使用像素值）
const radioInnerStyles = computed(() => {
    const radioSize = sizeConfig.value.size;
    return {
        width: `${radioSize}px`,
        height: `${radioSize}px`,
        marginTop: `${radioSize / -2}px`,
        marginLeft: `${radioSize / -2}px`
    };
});

// 容器样式
const wrapperClasses = computed(() => {
    const classes = ["vort-radio-wrapper"];
    if (isDisabled.value) classes.push("vort-radio-wrapper-disabled");
    if (props.class) classes.push(props.class);
    return classes;
});

// 文字样式
const labelClasses = computed(() => {
    const classes = ["vort-radio-label"];
    classes.push(`vort-radio-label-${size.value}`);
    if (isDisabled.value) classes.push("vort-radio-label-disabled");
    return classes;
});
</script>

<template>
    <label :class="wrapperClasses">
        <input
            type="radio"
            class="vort-radio-input"
            :name="radioGroupContext?.name.value"
            :value="value"
            :checked="isChecked"
            :disabled="isDisabled"
            @change="handleChange"
        />
        <span class="vort-radio-outer" :class="[isChecked && 'is-checked', isDisabled && 'is-disabled']" :style="radioStyles">
            <span class="vort-radio-inner" :style="radioInnerStyles" />
        </span>
        <span v-if="$slots.default" :class="labelClasses">
            <slot />
        </span>
    </label>
</template>

<style scoped>
.vort-radio-wrapper {
    display: inline-flex;
    align-items: center;
    cursor: pointer;
    user-select: none;
    min-height: 32px;
}

.vort-radio-wrapper-disabled {
    cursor: not-allowed;
}

.vort-radio-input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
}

.vort-radio-outer {
    border-color: var(--vort-border);
    border-style: solid;
    border-width: 1px;
    border-radius: 50%;
    transition: all var(--vort-duration-normal, 200ms);
    background: #fff;
    position: relative;
    display: inline-block;
    flex-shrink: 0;
}

.vort-radio-outer:not(.is-disabled):not(.is-checked):hover {
    border-color: var(--vort-primary);
}

.vort-radio-inner {
    position: absolute;
    top: 50%;
    left: 50%;
    display: block;
    background-color: var(--vort-primary);
    border-radius: 50%;
    transform: scale(0);
    opacity: 0;
    transition: all var(--vort-duration-normal, 200ms) cubic-bezier(0.78, 0.14, 0.15, 0.86);
    content: " ";
}

/* 选中状态 */
.vort-radio-outer.is-checked {
    border-color: var(--vort-primary);
    background: #fff;
}

.vort-radio-outer.is-checked .vort-radio-inner {
    transform: scale(0.5);
    opacity: 1;
    background-color: var(--vort-primary);
}

/* 禁用状态 */
.vort-radio-outer.is-disabled {
    border-color: var(--vort-border);
    background: rgba(0, 0, 0, 0.04);
    cursor: not-allowed;
}

.vort-radio-outer.is-disabled .vort-radio-inner {
    background-color: rgba(0, 0, 0, 0.25);
}

.vort-radio-outer.is-disabled.is-checked .vort-radio-inner {
    transform: scale(0.5);
    opacity: 1;
}

/* Label 样式 */
.vort-radio-label {
    margin-left: 8px;
    color: var(--vort-text);
}

.vort-radio-label-large {
    font-size: 16px;
}

.vort-radio-label-middle {
    font-size: 14px;
}

.vort-radio-label-small {
    font-size: 14px;
}

.vort-radio-label-disabled {
    color: rgba(0, 0, 0, 0.25);
}
</style>

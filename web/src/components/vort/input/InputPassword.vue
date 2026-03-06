<script setup lang="ts">
import { computed, ref, useAttrs } from "vue";
import VortInput from "./Input.vue";
import { EyeOutlined, EyeInvisibleOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortInputPassword", inheritAttrs: false });

/** Vort InputPassword - 密码输入框组件 */

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
    /** 是否有边框（兼容旧 API） */
    bordered?: boolean;
    /** 输入框占位文本 */
    placeholder?: string;
    /** 自定义类名 */
    class?: string;
    /** 是否显示切换按钮 */
    visibilityToggle?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    size: "middle",
    disabled: false,
    bordered: true,
    visibilityToggle: true
});

const emit = defineEmits<{
    "update:modelValue": [value: string];
    change: [event: Event];
    input: [event: Event];
    focus: [event: FocusEvent];
    blur: [event: FocusEvent];
    pressEnter: [event: KeyboardEvent];
}>();

const attrs = useAttrs();
const inputRef = ref<InstanceType<typeof VortInput> | null>(null);
const isVisible = ref(false);

// 计算 input type
const inputType = computed(() => (isVisible.value ? "text" : "password"));

// 切换密码可见性
const toggleVisibility = () => {
    if (!props.disabled) {
        isVisible.value = !isVisible.value;
    }
};

// 透传给 Input 的 props
const inputProps = computed(() => ({
    modelValue: props.modelValue,
    defaultValue: props.defaultValue,
    size: props.size,
    status: props.status,
    variant: props.variant,
    disabled: props.disabled,
    bordered: props.bordered,
    placeholder: props.placeholder,
    class: props.class
}));

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
    <VortInput
        ref="inputRef"
        :type="inputType"
        v-bind="{ ...inputProps, ...attrs }"
        @update:model-value="(val: string) => emit('update:modelValue', val)"
        @change="(e: Event) => emit('change', e)"
        @input="(e: Event) => emit('input', e)"
        @focus="(e: FocusEvent) => emit('focus', e)"
        @blur="(e: FocusEvent) => emit('blur', e)"
        @press-enter="(e: KeyboardEvent) => emit('pressEnter', e)"
    >
        <!-- 透传 prefix slot -->
        <template v-if="$slots.prefix" #prefix>
            <slot name="prefix" />
        </template>

        <!-- 密码切换图标 + 透传 suffix slot -->
        <template #suffix>
            <slot name="suffix" />
            <span
                v-if="visibilityToggle"
                class="vort-input-password-icon"
                :class="{ 'vort-input-password-icon-disabled': disabled }"
                role="button"
                tabindex="-1"
                :aria-label="isVisible ? '隐藏密码' : '显示密码'"
                @click="toggleVisibility"
                @mousedown.prevent
            >
                <EyeInvisibleOutlined v-if="isVisible" />
                <EyeOutlined v-else />
            </span>
        </template>
    </VortInput>
</template>

<style scoped>
/* ========================================
   InputPassword 特有样式 - 密码切换图标
   ======================================== */
.vort-input-password-icon {
    display: flex;
    align-items: center;
    font-size: 14px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: pointer;
    transition: color var(--vort-transition-colors, 0.1s);
}

.vort-input-password-icon:hover {
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
}

.vort-input-password-icon-disabled {
    cursor: not-allowed;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

.vort-input-password-icon-disabled:hover {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}
</style>

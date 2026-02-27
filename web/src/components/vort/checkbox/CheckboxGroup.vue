<script setup lang="ts">
import { computed, provide, toRef, watch, ref } from "vue";

defineOptions({ name: "VortCheckboxGroup" });

/** Vort CheckboxGroup - 复选框组组件 */

interface CheckboxOption {
    label: string;
    value: string | number;
    disabled?: boolean;
}

interface Props {
    /** 当前选中的值（v-model） */
    modelValue?: (string | number)[];
    /** 默认选中的值 */
    defaultValue?: (string | number)[];
    /** 是否禁用整组 */
    disabled?: boolean;
    /** 以配置形式设置子元素 */
    options?: (string | number | CheckboxOption)[];
    /** input 元素的 name 属性 */
    name?: string;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false
});

const emit = defineEmits<{
    "update:modelValue": [value: (string | number)[]];
    change: [checkedValues: (string | number)[]];
}>();

// 内部值管理
const innerValue = ref<(string | number)[]>(props.modelValue ?? props.defaultValue ?? []);

// 监听 modelValue 变化
watch(
    () => props.modelValue,
    (newVal) => {
        if (newVal !== undefined) {
            innerValue.value = [...newVal];
        }
    }
);

// 提供给子组件的上下文
provide("checkboxGroupContext", {
    name: toRef(props, "name"),
    disabled: toRef(props, "disabled"),
    value: innerValue,
    onChange: (value: string | number, checked: boolean, _event: Event) => {
        const newValues = [...innerValue.value];
        if (checked) {
            if (!newValues.includes(value)) {
                newValues.push(value);
            }
        } else {
            const index = newValues.indexOf(value);
            if (index > -1) {
                newValues.splice(index, 1);
            }
        }
        innerValue.value = newValues;
        emit("update:modelValue", newValues);
        emit("change", newValues);
    }
});

// 格式化 options
const normalizedOptions = computed(() => {
    if (!props.options) return [];
    return props.options.map((opt) => {
        if (typeof opt === "string" || typeof opt === "number") {
            return { label: String(opt), value: opt, disabled: false };
        }
        return opt;
    });
});

// ========== 类名计算 ==========

/** 容器类名 */
const groupClasses = computed(() => {
    const classes = ["vort-checkbox-group"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div :class="groupClasses" role="group">
        <!-- 使用 options 配置 -->
        <template v-if="options && options.length > 0">
            <Checkbox v-for="opt in normalizedOptions" :key="opt.value" :value="opt.value" :disabled="opt.disabled">
                {{ opt.label }}
            </Checkbox>
        </template>

        <!-- 使用 slot -->
        <slot v-else />
    </div>
</template>

<script lang="ts">
import Checkbox from "./Checkbox.vue";

export default {
    components: {
        Checkbox
    }
};
</script>

<style scoped>
/* ========================================
   CheckboxGroup 容器
   ======================================== */
.vort-checkbox-group {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 8px 24px;
}
</style>

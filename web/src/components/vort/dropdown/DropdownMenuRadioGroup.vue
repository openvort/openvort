<script setup lang="ts">
/**
 * Vort DropdownMenuRadioGroup - 单选菜单组组件
 */
import { computed } from "vue";
import { DropdownMenuRadioGroup as RekaDropdownMenuRadioGroup } from "reka-ui";
import type { AcceptableValue } from "reka-ui";

defineOptions({ name: "VortDropdownMenuRadioGroup" });

interface Props {
    /** 选中的值 */
    modelValue?: AcceptableValue;
    /** 自定义类名 */
    class?: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
    "update:modelValue": [value: AcceptableValue];
}>();

const handleModelValueUpdate = (value: AcceptableValue) => {
    emit("update:modelValue", value);
};

const groupClasses = computed(() => {
    const classes = ["vort-dropdown-menu-radio-group"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <RekaDropdownMenuRadioGroup :model-value="props.modelValue" :class="groupClasses" @update:model-value="handleModelValueUpdate">
        <slot />
    </RekaDropdownMenuRadioGroup>
</template>

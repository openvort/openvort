<script setup lang="ts">
/**
 * Vort DropdownMenuRadioGroup - 单选菜单组组件
 */
import { computed, provide } from "vue";

defineOptions({ name: "VortDropdownMenuRadioGroup" });

interface Props {
    /** 选中的值 */
    modelValue?: string;
    /** 自定义类名 */
    class?: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
    "update:modelValue": [value: string];
}>();

provide("vortDropdownRadioContext", {
    value: computed(() => props.modelValue),
    select: (val: string) => emit("update:modelValue", val)
});

const groupClasses = computed(() => {
    const classes = ["vort-dropdown-menu-radio-group"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div :class="groupClasses" role="group">
        <slot />
    </div>
</template>

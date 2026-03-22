<script setup lang="ts">
/**
 * Vort DropdownMenuCheckboxItem - 可选中的菜单项组件
 */
import { computed } from "vue";
import { DropdownMenuCheckboxItem as RekaDropdownMenuCheckboxItem, DropdownMenuItemIndicator } from "reka-ui";
import { Check } from "lucide-vue-next";

defineOptions({ name: "VortDropdownMenuCheckboxItem" });

interface Props {
    /** 选中状态 */
    checked?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    checked: false,
    disabled: false
});

const emit = defineEmits<{
    "update:checked": [checked: boolean];
}>();

const itemClasses = computed(() => {
    const classes = ["vort-dropdown-menu-checkbox-item"];
    if (props.class) classes.push(props.class);
    return classes;
});

const handleCheckedChange = (checked: boolean) => {
    emit("update:checked", checked);
};
</script>

<template>
    <RekaDropdownMenuCheckboxItem :class="itemClasses" :checked="checked" :disabled="disabled" @update:checked="handleCheckedChange">
        <DropdownMenuItemIndicator class="vort-dropdown-menu-item-indicator">
            <Check class="vort-dropdown-check-icon" />
        </DropdownMenuItemIndicator>
        <slot />
    </RekaDropdownMenuCheckboxItem>
</template>

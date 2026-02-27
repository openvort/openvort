<script setup lang="ts">
/**
 * Vort DropdownMenuRadioItem - 单选菜单项组件
 */
import { computed } from "vue";
import { DropdownMenuRadioItem as RekaDropdownMenuRadioItem, DropdownMenuItemIndicator } from "reka-ui";

defineOptions({ name: "VortDropdownMenuRadioItem" });

interface Props {
    /** 选项值 */
    value: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false
});

const itemClasses = computed(() => {
    const classes = ["vort-dropdown-menu-radio-item"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <RekaDropdownMenuRadioItem :class="itemClasses" :value="value" :disabled="disabled">
        <DropdownMenuItemIndicator class="vort-dropdown-menu-item-indicator">
            <svg class="vort-dropdown-radio-icon" width="8" height="8" viewBox="0 0 8 8" fill="currentColor">
                <circle cx="4" cy="4" r="4" />
            </svg>
        </DropdownMenuItemIndicator>
        <slot />
    </RekaDropdownMenuRadioItem>
</template>

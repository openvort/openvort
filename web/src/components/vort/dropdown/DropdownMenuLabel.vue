<script setup lang="ts">
/**
 * Vort DropdownMenuLabel - 下拉菜单标签组件
 *
 * 用于菜单分组标题
 */
import { computed } from "vue";
import { DropdownMenuLabel as RekaDropdownMenuLabel } from "reka-ui";

defineOptions({ name: "VortDropdownMenuLabel" });

interface Props {
    /** 自定义类名 */
    class?: string;
}

const props = defineProps<Props>();

const labelClasses = computed(() => {
    const classes = ["vort-dropdown-menu-label"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <RekaDropdownMenuLabel :class="labelClasses">
        <slot />
    </RekaDropdownMenuLabel>
</template>

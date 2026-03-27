<script setup lang="ts">
/** Vort DropdownMenuGroup - 下拉菜单分组组件 */
import { computed } from "vue";

defineOptions({ name: "VortDropdownMenuGroup" });

interface Props {
    /** 自定义类名 */
    class?: string;
}

const props = defineProps<Props>();

const groupClasses = computed(() => {
    const classes = ["vort-dropdown-menu-group"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div :class="groupClasses" role="group">
        <slot />
    </div>
</template>

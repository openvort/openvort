<script setup lang="ts">
import { computed } from "vue";

defineOptions({ name: "VortMenuDivider" });

/**
 * Vort MenuDivider - 菜单分割线组件
 */

interface Props {
    /** 是否虚线 */
    dashed?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    dashed: false
});

// 样式类
const dividerClasses = computed(() => {
    const classes = ["vort-menu-divider"];
    if (props.dashed) classes.push("vort-menu-divider--dashed");
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <li :class="dividerClasses" role="separator" />
</template>

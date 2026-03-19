<script setup lang="ts">
/** Vort DropdownMenuItem - 下拉菜单项组件 */
import { computed } from "vue";
import { DropdownMenuItem as RekaDropdownMenuItem } from "reka-ui";

defineOptions({ name: "VortDropdownMenuItem" });

interface Props {
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否为危险项（红色） */
    danger?: boolean;
    /** 菜单图标 */
    icon?: string;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false,
    danger: false,
    icon: undefined
});

const emit = defineEmits<{
    /** 点击菜单项时触发 */
    click: [event: Event];
}>();

const itemClasses = computed(() => {
    const classes = ["vort-dropdown-menu-item"];
    if (props.danger) classes.push("vort-dropdown-menu-item-danger");
    if (props.class) classes.push(props.class);
    return classes;
});

const handleSelect = (event: Event) => {
    emit("click", event);
};
</script>

<template>
    <RekaDropdownMenuItem :class="itemClasses" :disabled="disabled" @select="handleSelect">
        <span v-if="$slots.icon || icon" class="vort-dropdown-menu-item-icon">
            <slot name="icon">{{ icon }}</slot>
        </span>
        <slot />
    </RekaDropdownMenuItem>
</template>

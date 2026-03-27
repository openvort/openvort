<script setup lang="ts">
/** Vort DropdownMenuItem - 下拉菜单项组件 */
import { computed, inject } from "vue";
import type { VortDropdownContext } from "./Dropdown.vue";

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
    click: [event: Event];
}>();

const ctx = inject<VortDropdownContext>("vortDropdownContext");

const itemClasses = computed(() => {
    const classes = ["vort-dropdown-menu-item"];
    if (props.danger) classes.push("vort-dropdown-menu-item-danger");
    if (props.class) classes.push(props.class);
    return classes;
});

const handleClick = (event: Event) => {
    if (props.disabled) return;
    emit("click", event);
    ctx?.close();
};

const handleKeydown = (e: KeyboardEvent) => {
    if (props.disabled) return;
    if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleClick(e);
    }
};
</script>

<template>
    <div
        :class="itemClasses"
        role="menuitem"
        :tabindex="disabled ? undefined : -1"
        :data-disabled="disabled ? '' : undefined"
        @click="handleClick"
        @keydown="handleKeydown"
    >
        <span v-if="$slots.icon || icon" class="vort-dropdown-menu-item-icon">
            <slot name="icon">{{ icon }}</slot>
        </span>
        <slot />
    </div>
</template>

<script setup lang="ts">
/**
 * Vort DropdownMenuCheckboxItem - 可选中的菜单项组件
 */
import { computed } from "vue";
import { CheckOutlined } from "@/components/vort/icons";

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

const handleClick = () => {
    if (props.disabled) return;
    emit("update:checked", !props.checked);
};

const handleKeydown = (e: KeyboardEvent) => {
    if (props.disabled) return;
    if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleClick();
    }
};
</script>

<template>
    <div
        :class="itemClasses"
        role="menuitemcheckbox"
        :tabindex="disabled ? undefined : -1"
        :data-disabled="disabled ? '' : undefined"
        :data-state="checked ? 'checked' : 'unchecked'"
        :aria-checked="checked"
        @click="handleClick"
        @keydown="handleKeydown"
    >
        <span v-if="checked" class="vort-dropdown-menu-item-indicator">
            <CheckOutlined class="vort-dropdown-check-icon" />
        </span>
        <slot />
    </div>
</template>

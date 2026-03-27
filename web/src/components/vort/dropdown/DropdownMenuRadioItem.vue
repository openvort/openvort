<script setup lang="ts">
/**
 * Vort DropdownMenuRadioItem - 单选菜单项组件
 */
import { computed, inject } from "vue";
import type { ComputedRef } from "vue";

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

const radioCtx = inject<{ value: ComputedRef<string | undefined>; select: (val: string) => void }>("vortDropdownRadioContext");

const isChecked = computed(() => radioCtx?.value.value === props.value);

const itemClasses = computed(() => {
    const classes = ["vort-dropdown-menu-radio-item"];
    if (props.class) classes.push(props.class);
    return classes;
});

const handleClick = () => {
    if (props.disabled) return;
    radioCtx?.select(props.value);
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
        role="menuitemradio"
        :tabindex="disabled ? undefined : -1"
        :data-disabled="disabled ? '' : undefined"
        :data-state="isChecked ? 'checked' : 'unchecked'"
        :aria-checked="isChecked"
        @click="handleClick"
        @keydown="handleKeydown"
    >
        <span v-if="isChecked" class="vort-dropdown-menu-item-indicator">
            <svg class="vort-dropdown-radio-icon" width="8" height="8" viewBox="0 0 8 8" fill="currentColor">
                <circle cx="4" cy="4" r="4" />
            </svg>
        </span>
        <slot />
    </div>
</template>

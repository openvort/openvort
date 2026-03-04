<script setup lang="ts">
import type { SelectTriggerProps } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { computed } from "vue";
import { reactiveOmit } from "@vueuse/core";
import { ChevronDown } from "lucide-vue-next";
import { SelectIcon, SelectTrigger, useForwardProps } from "reka-ui";

const props = withDefaults(defineProps<SelectTriggerProps & { class?: HTMLAttributes["class"]; size?: "sm" | "default" }>(), { size: "default" });

const delegatedProps = reactiveOmit(props, "class", "size");
const forwardedProps = useForwardProps(delegatedProps);

const triggerClasses = computed(() => {
    const classes = ["vort-select-trigger"];
    if (props.size === "sm") classes.push("vort-select-trigger-sm");
    if (props.class) classes.push(props.class as string);
    return classes;
});
</script>

<template>
    <SelectTrigger data-slot="select-trigger" :data-size="size" v-bind="forwardedProps" :class="triggerClasses">
        <slot />
        <SelectIcon as-child>
            <ChevronDown class="vort-select-trigger-icon" />
        </SelectIcon>
    </SelectTrigger>
</template>

<style scoped>
.vort-select-trigger {
    display: flex;
    width: fit-content;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    border-radius: var(--vort-border-radius, 6px);
    border: 1px solid var(--vort-border);
    background: transparent;
    padding: 8px 12px;
    font-size: 14px;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    white-space: nowrap;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
    transition:
        color 200ms,
        box-shadow 200ms;
    outline: none;
    height: 36px;
}

.vort-select-trigger-sm {
    height: 32px;
}

.vort-select-trigger[data-placeholder] {
    color: var(--vort-text-quaternary);
}

.vort-select-trigger:focus-visible {
    border-color: var(--vort-primary);
    box-shadow: 0 0 0 3px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

.vort-select-trigger:disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

.vort-select-trigger-icon {
    width: 16px;
    height: 16px;
    color: var(--vort-text-quaternary);
}

/* svg 图标样式 */
.vort-select-trigger :deep(svg) {
    pointer-events: none;
    flex-shrink: 0;
}

.vort-select-trigger :deep(svg:not(.vort-select-trigger-icon)) {
    width: 16px;
    height: 16px;
}

/* 值容器样式 */
.vort-select-trigger :deep([data-slot="select-value"]) {
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
    display: flex;
    align-items: center;
    gap: 8px;
}
</style>

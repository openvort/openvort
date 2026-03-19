<script setup lang="ts">
import type { SelectItemProps } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { computed } from "vue";
import { reactiveOmit } from "@vueuse/core";
import { SelectItem, SelectItemText, useForwardProps } from "reka-ui";

const props = defineProps<SelectItemProps & { class?: HTMLAttributes["class"] }>();

const delegatedProps = reactiveOmit(props, "class");

const forwardedProps = useForwardProps(delegatedProps);

const itemClasses = computed(() => {
    const classes = ["vort-select-item"];
    if (props.class) classes.push(props.class as string);
    return classes;
});
</script>

<template>
    <SelectItem data-slot="select-item" v-bind="forwardedProps" :class="itemClasses">
        <SelectItemText>
            <slot />
        </SelectItemText>
    </SelectItem>
</template>

<style scoped>
.vort-select-item {
    position: relative;
    display: flex;
    width: 100%;
    cursor: pointer;
    align-items: center;
    gap: 8px;
    border-radius: var(--vort-border-radius-sm, 4px);
    padding: 6px 32px 6px 8px;
    font-size: 14px;
    outline: none;
    user-select: none;
    transition: background-color 150ms;
}

.vort-select-item:hover {
    background: var(--vort-fill-quaternary, rgba(0, 0, 0, 0.04));
    color: var(--vort-text);
}

.vort-select-item[data-disabled] {
    pointer-events: none;
    opacity: 0.5;
}

.vort-select-item[data-state="checked"] {
    background: var(--vort-primary-bg);
    font-weight: 500;
}

/* svg 图标样式 */
.vort-select-item :deep(svg) {
    pointer-events: none;
    flex-shrink: 0;
    width: 16px;
    height: 16px;
    color: var(--vort-text-tertiary);
}

/* 最后一个 span（通常包含 SelectItemText 内容） */
.vort-select-item :deep(span:last-child) {
    display: flex;
    align-items: center;
    gap: 8px;
}
</style>

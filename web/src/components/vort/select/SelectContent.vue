<script setup lang="ts">
import type { SelectContentEmits, SelectContentProps } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { computed } from "vue";
import { reactiveOmit } from "@vueuse/core";
import { SelectContent, SelectPortal, SelectViewport, useForwardPropsEmits } from "reka-ui";
import { SelectScrollDownButton, SelectScrollUpButton } from ".";

defineOptions({
    inheritAttrs: false
});

const props = withDefaults(defineProps<SelectContentProps & { class?: HTMLAttributes["class"] }>(), {
    position: "popper",
    bodyLock: false // 禁用 body 滚动锁定
});
const emits = defineEmits<SelectContentEmits>();

const delegatedProps = reactiveOmit(props, "class");

const forwarded = useForwardPropsEmits(delegatedProps, emits);

const contentClasses = computed(() => {
    const classes = ["vort-select-content"];
    if (props.position === "popper") classes.push("vort-select-content-popper");
    if (props.class) classes.push(props.class as string);
    return classes;
});

const viewportClasses = computed(() => {
    const classes = ["vort-select-viewport"];
    if (props.position === "popper") classes.push("vort-select-viewport-popper");
    return classes;
});
</script>

<template>
    <SelectPortal>
        <SelectContent data-slot="select-content" v-bind="{ ...$attrs, ...forwarded }" :class="contentClasses">
            <SelectScrollUpButton />
            <SelectViewport :class="viewportClasses">
                <slot />
            </SelectViewport>
            <SelectScrollDownButton />
        </SelectContent>
    </SelectPortal>
</template>

<style>
/* 覆盖 reka-ui 的 popper wrapper z-index
 * Select 的 popper wrapper 默认 z-index 是 50，需要用 !important 覆盖
 * 使用 1050 确保在 Dialog(1000) 之上
 */
[data-reka-popper-content-wrapper]:has([data-slot="select-content"]) {
    z-index: 1050 !important;
}
</style>

<style scoped>
.vort-select-content {
    position: relative;
    max-height: var(--reka-select-content-available-height);
    min-width: 8rem;
    overflow-x: hidden;
    overflow-y: auto;
    border-radius: var(--vort-border-radius-lg, 8px);
    border: 1px solid var(--vort-border-secondary);
    background: var(--vort-bg, #fff);
    color: var(--vort-text);
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
}

/* 动画 */
.vort-select-content[data-state="open"] {
    animation: vortSelectIn 0.2s ease-out;
}

.vort-select-content[data-state="closed"] {
    animation: vortSelectOut 0.15s ease-in;
}

@keyframes vortSelectIn {
    from {
        opacity: 0;
        transform: scale(0.95);
    }
    to {
        opacity: 1;
        transform: scale(1);
    }
}

@keyframes vortSelectOut {
    from {
        opacity: 1;
        transform: scale(1);
    }
    to {
        opacity: 0;
        transform: scale(0.95);
    }
}

/* Popper 位置偏移 */
.vort-select-content-popper[data-side="bottom"] {
    transform: translateY(4px);
}

.vort-select-content-popper[data-side="top"] {
    transform: translateY(-4px);
}

.vort-select-content-popper[data-side="left"] {
    transform: translateX(-4px);
}

.vort-select-content-popper[data-side="right"] {
    transform: translateX(4px);
}

/* Viewport */
.vort-select-viewport {
    padding: 4px;
}

.vort-select-viewport-popper {
    width: 100%;
    min-width: var(--reka-select-trigger-width);
    scroll-margin: 4px;
}
</style>

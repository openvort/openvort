<script setup lang="ts">
import type { SelectLabelProps } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { computed } from "vue";
import { SelectLabel } from "reka-ui";

const props = defineProps<SelectLabelProps & { class?: HTMLAttributes["class"] }>();

const labelClasses = computed(() => {
    const classes = ["vort-select-label"];
    if (props.class) classes.push(props.class as string);
    return classes;
});
</script>

<template>
    <SelectLabel data-slot="select-label" :class="labelClasses">
        <slot />
    </SelectLabel>
</template>

<style scoped>
.vort-select-label {
    padding: 6px 8px;
    font-size: 12px;
    color: var(--vort-text-tertiary);
}
</style>

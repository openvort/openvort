<script setup lang="ts">
import type { SelectSeparatorProps } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { computed } from "vue";
import { reactiveOmit } from "@vueuse/core";
import { SelectSeparator } from "reka-ui";

const props = defineProps<SelectSeparatorProps & { class?: HTMLAttributes["class"] }>();

const delegatedProps = reactiveOmit(props, "class");

const separatorClasses = computed(() => {
    const classes = ["vort-select-separator"];
    if (props.class) classes.push(props.class as string);
    return classes;
});
</script>

<template>
    <SelectSeparator data-slot="select-separator" v-bind="delegatedProps" :class="separatorClasses" />
</template>

<style scoped>
.vort-select-separator {
    pointer-events: none;
    margin: 4px -4px;
    height: 1px;
    background: var(--vort-border-secondary);
}
</style>

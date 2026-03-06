<script setup lang="ts">
import type { SelectScrollUpButtonProps } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { computed } from "vue";
import { reactiveOmit } from "@vueuse/core";
import { ChevronUp } from "lucide-vue-next";
import { SelectScrollUpButton, useForwardProps } from "reka-ui";

const props = defineProps<SelectScrollUpButtonProps & { class?: HTMLAttributes["class"] }>();

const delegatedProps = reactiveOmit(props, "class");

const forwardedProps = useForwardProps(delegatedProps);

const buttonClasses = computed(() => {
    const classes = ["vort-select-scroll-button"];
    if (props.class) classes.push(props.class as string);
    return classes;
});
</script>

<template>
    <SelectScrollUpButton data-slot="select-scroll-up-button" v-bind="forwardedProps" :class="buttonClasses">
        <slot>
            <ChevronUp class="vort-select-scroll-icon" />
        </slot>
    </SelectScrollUpButton>
</template>

<style scoped>
.vort-select-scroll-button {
    display: flex;
    cursor: default;
    align-items: center;
    justify-content: center;
    padding: 4px 0;
}

.vort-select-scroll-icon {
    width: 16px;
    height: 16px;
}
</style>

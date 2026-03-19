<script setup lang="ts">
import type { SelectScrollDownButtonProps } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { computed } from "vue";
import { reactiveOmit } from "@vueuse/core";
import { ChevronDown } from "lucide-vue-next";
import { SelectScrollDownButton, useForwardProps } from "reka-ui";

const props = defineProps<SelectScrollDownButtonProps & { class?: HTMLAttributes["class"] }>();

const delegatedProps = reactiveOmit(props, "class");

const forwardedProps = useForwardProps(delegatedProps);

const buttonClasses = computed(() => {
    const classes = ["vort-select-scroll-button"];
    if (props.class) classes.push(props.class as string);
    return classes;
});
</script>

<template>
    <SelectScrollDownButton data-slot="select-scroll-down-button" v-bind="forwardedProps" :class="buttonClasses">
        <slot>
            <ChevronDown class="vort-select-scroll-icon" />
        </slot>
    </SelectScrollDownButton>
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

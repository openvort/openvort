<script lang="ts">
const popoverSelectInstances = new Set<() => void>();

const closeOtherPopoverSelects = (currentClose: () => void) => {
    popoverSelectInstances.forEach((close) => {
        if (close !== currentClose) {
            close();
        }
    });
};

export type { PopoverSelectProps, PopoverSelectSize } from "./types";
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from "vue";
import { Popover } from "@openvort/vort-ui";
import "./popover-select.css";
import { DownOutlined } from "@openvort/vort-ui";
import { popoverSelectSizeProp } from "./types";
import type { PopoverSelectProps } from "./types";

defineOptions({
    name: "VortPopoverSelect"
});

const props = withDefaults(defineProps<PopoverSelectProps>(), {
    disabled: false,
    size: "middle",
    placeholder: "请选择",
    showSearch: false,
    searchPlaceholder: "搜索...",
    dropdownWidth: 240,
    dropdownMaxHeight: 256,
    placement: "bottomLeft",
    triggerClass: "",
    dropdownClass: "",
    bordered: true,
    clearSearchOnClose: true
});

const open = defineModel<boolean>("open", { default: false });
const keyword = defineModel<string>("keyword", { default: "" });

const emit = defineEmits<{
    openChange: [open: boolean];
    search: [value: string];
}>();

const normalizedWidth = computed(() => {
    if (typeof props.dropdownWidth === "number") {
        return `${props.dropdownWidth}px`;
    }
    return props.dropdownWidth || "240px";
});

const overlayStyle = computed<Record<string, string>>(() => ({
    width: normalizedWidth.value,
    padding: "0",
    maxWidth: "none",
    minHeight: "0"
}));

const triggerClasses = computed(() => {
    const classes = ["vort-popover-select-trigger", `vort-popover-select-${props.size}`];
    if (props.bordered) {
        classes.push("vort-popover-select-bordered");
    } else {
        classes.push("vort-popover-select-borderless");
    }
    if (open.value) {
        classes.push("is-open");
    }
    if (props.disabled) {
        classes.push("is-disabled");
    }
    if (props.triggerClass) {
        classes.push(props.triggerClass);
    }
    return classes;
});

const overlayClass = computed(() => {
    const classes = [
        "vort-popover-select-dropdown",
        `vort-popover-select-${props.placement}`
    ];
    if (props.dropdownClass) {
        classes.push(props.dropdownClass);
    }
    return classes.join(" ");
});

const closeThis = () => {
    open.value = false;
};

popoverSelectInstances.add(closeThis);

onBeforeUnmount(() => {
    popoverSelectInstances.delete(closeThis);
});

watch(open, (value) => {
    if (value) {
        closeOtherPopoverSelects(closeThis);
    } else if (props.clearSearchOnClose && keyword.value) {
        keyword.value = "";
    }
    emit("openChange", value);
});

watch(keyword, (value) => {
    emit("search", value);
});
</script>

<template>
    <Popover
        v-model:open="open"
        trigger="click"
        :placement="placement"
        :arrow="false"
        :disabled="disabled"
        :overlay-class="overlayClass"
        :overlay-style="overlayStyle"
    >
        <slot name="trigger" :open="open" :keyword="keyword">
            <button
                type="button"
                :class="triggerClasses"
                :disabled="disabled"
            >
                <span class="vort-popover-select-placeholder">{{ placeholder }}</span>
                <DownOutlined
                    class="vort-popover-select-arrow"
                    :class="{ 'vort-popover-select-arrow-open': open }"
                />
            </button>
        </slot>

        <template #content>
            <div class="vort-popover-select-panel" @click.stop>
                <div v-if="showSearch" class="vort-popover-select-search mb-2">
                    <slot name="search" :keyword="keyword">
                        <VortInput
                            v-model="keyword"
                            :placeholder="searchPlaceholder"
                            class="w-full"
                        />
                    </slot>
                </div>
                <VortScrollbar class="vort-popover-select-body" :max-height="dropdownMaxHeight">
                    <slot :open="open" :keyword="keyword" />
                </VortScrollbar>
                <div v-if="$slots.footer" class="vort-popover-select-footer">
                    <slot name="footer" :open="open" :keyword="keyword" />
                </div>
            </div>
        </template>
    </Popover>
</template>

<style scoped>
.vort-popover-select-trigger {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    background: #fff;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    transition: var(--vort-transition-all, all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1));
}

.vort-popover-select-bordered {
    border: 1px solid var(--vort-border, #d9d9d9);
    border-radius: var(--vort-radius, 6px);
}

.vort-popover-select-bordered:hover:not(.is-disabled),
.vort-popover-select-bordered.is-open:not(.is-disabled) {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px rgba(20, 86, 240, 0.1);
}

.vort-popover-select-borderless {
    border: 1px solid transparent;
    border-radius: var(--vort-radius, 6px);
}

.vort-popover-select-borderless:hover:not(.is-disabled),
.vort-popover-select-borderless.is-open:not(.is-disabled) {
    background: rgba(20, 86, 240, 0.04);
}

.vort-popover-select-large {
    min-height: var(--vort-height-lg, 40px);
    padding: 4px 11px;
    font-size: var(--vort-font-size-md, 16px);
}

.vort-popover-select-middle {
    min-height: var(--vort-height-md, 32px);
    padding: 4px 11px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-popover-select-small {
    min-height: var(--vort-height-sm, 24px);
    padding: 2px 7px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-popover-select-trigger.is-disabled {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    background: rgba(0, 0, 0, 0.04);
    cursor: not-allowed;
}

.vort-popover-select-placeholder {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.45));
}

.vort-popover-select-arrow {
    flex-shrink: 0;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    transition: transform 0.2s ease;
}

.vort-popover-select-arrow-open {
    transform: rotate(180deg);
}

.vort-popover-select-panel {
    display: flex;
    flex-direction: column;
    background: #fff;
    border-radius: var(--vort-radius, 6px);
}

.vort-popover-select-search {
    padding: 12px 8px 0px 8px;
}

.vort-popover-select-body {
    width: 100%;
}

.vort-popover-select-footer {
    border-top: 1px solid var(--vort-border, #f0f0f0);
    background: #fff;
}
</style>

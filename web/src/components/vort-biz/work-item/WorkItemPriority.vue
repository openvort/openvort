<script setup lang="ts">
import PopoverSelect from "@/components/vort-biz/popover-select/PopoverSelect.vue";
import type { Priority } from "./WorkItemTable.types";

interface Props {
    modelValue?: Priority;
    disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    modelValue: "none",
    disabled: false
});

const emit = defineEmits<{
    (e: "update:modelValue", value: Priority): void;
    (e: "change", value: Priority): void;
    (e: "click", event: MouseEvent): void;
}>();

const priorityOptions: Array<{ label: string; value: Priority }> = [
    { label: "紧急", value: "urgent" },
    { label: "高", value: "high" },
    { label: "中", value: "medium" },
    { label: "低", value: "low" },
    { label: "无优先级", value: "none" }
];

const priorityLabelMap: Record<Priority, string> = {
    urgent: "紧急",
    high: "高",
    medium: "中",
    low: "低",
    none: "无优先级"
};

const priorityClassMap: Record<Priority, string> = {
    urgent: "text-red-500 border-red-500 bg-red-50",
    high: "text-amber-500 border-amber-500 bg-amber-50",
    medium: "text-blue-500 border-blue-500 bg-blue-50",
    low: "text-emerald-500 border-emerald-500 bg-emerald-50",
    none: "text-gray-400 border-gray-300 bg-gray-50"
};

const open = defineModel<boolean>("open", { default: false });

const handleSelect = (value: Priority) => {
    emit("update:modelValue", value);
    emit("change", value);
    open.value = false;
};

const handleTriggerClick = (event: MouseEvent) => {
    emit("click", event);
};
</script>

<template>
    <PopoverSelect
        v-model:open="open"
        :disabled="disabled"
        placeholder="优先级"
        :show-search="false"
        :dropdown-width="140"
        :dropdown-max-height="220"
        :bordered="false"
    >
        <template #trigger>
            <slot>
                <div class="priority-cell-trigger" :class="{ 'is-disabled': disabled }" @click="handleTriggerClick">
                    <span class="priority-pill" :class="priorityClassMap[modelValue]">
                        {{ priorityLabelMap[modelValue] }}
                    </span>
                </div>
            </slot>
        </template>

        <div class="priority-picker-content">
            <div
                v-for="opt in priorityOptions"
                :key="opt.value"
                class="priority-picker-row"
                :class="{ 'is-active': modelValue === opt.value, 'is-disabled': disabled }"
                @click.stop="!disabled && handleSelect(opt.value)"
            >
                <span class="priority-pill" :class="priorityClassMap[opt.value]">
                    {{ opt.label }}
                </span>
            </div>
        </div>
    </PopoverSelect>
</template>

<style scoped>
.priority-cell-trigger {
    padding: 2px 8px;
    cursor: pointer;
}

.priority-cell-trigger.is-disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

.priority-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    border: 1px solid;
}

.priority-picker-content {
    padding: 4px;
}

.priority-picker-row {
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s ease;
}

.priority-picker-row:hover {
    background: rgba(0, 0, 0, 0.04);
}

.priority-picker-row.is-active {
    background: #eff6ff;
}

.priority-picker-row.is-disabled {
    cursor: not-allowed;
    opacity: 0.5;
}
</style>

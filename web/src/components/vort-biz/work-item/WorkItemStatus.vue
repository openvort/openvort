<script setup lang="ts">
import { computed } from "vue";
import PopoverSelect from "@/components/vort-biz/popover-select/PopoverSelect.vue";
import type { Status, StatusOption } from "./WorkItemTable.types";

interface Props {
    modelValue?: Status;
    options?: StatusOption[];
    disabled?: boolean;
    placeholder?: string;
}

const props = withDefaults(defineProps<Props>(), {
    modelValue: "" as any,
    options: () => [],
    disabled: false,
    placeholder: "状态"
});

const emit = defineEmits<{
    (e: "update:modelValue", value: Status): void;
    (e: "change", value: Status): void;
    (e: "click", event: MouseEvent): void;
}>();

const open = defineModel<boolean>("open", { default: false });
const keyword = defineModel<string>("keyword", { default: "" });

const statusClassMap: Record<string, string> = {
    待确认: "bg-gray-100 text-gray-400 border-gray-200",
    修复中: "bg-blue-50 text-blue-600 border-blue-100",
    已修复: "bg-blue-50 text-blue-600 border-blue-100",
    延期处理: "bg-sky-100 text-sky-700 border-sky-200",
    设计如此: "bg-amber-100 text-amber-600 border-amber-200",
    再次打开: "bg-red-100 text-red-600 border-red-200",
    无法复现: "bg-amber-100 text-amber-600 border-amber-200",
    已关闭: "bg-gray-100 text-gray-700 border-gray-200",
    暂时搁置: "bg-gray-100 text-gray-500 border-gray-200",
    已取消: "bg-red-100 text-red-600 border-red-200",
    意向: "bg-slate-100 text-slate-600 border-slate-200",
    暂搁置: "bg-slate-100 text-slate-500 border-slate-200",
    设计中: "bg-indigo-100 text-indigo-600 border-indigo-200",
    开发中: "bg-blue-100 text-blue-600 border-blue-200",
    开发完成: "bg-cyan-100 text-cyan-700 border-cyan-200",
    测试完成: "bg-violet-100 text-violet-700 border-violet-200",
    待发布: "bg-amber-100 text-amber-700 border-amber-200",
    发布完成: "bg-emerald-100 text-emerald-700 border-emerald-200",
    已完成: "bg-emerald-100 text-emerald-700 border-emerald-200",
    待办的: "bg-slate-100 text-slate-600 border-slate-200",
    进行中: "bg-blue-100 text-blue-600 border-blue-200",
};

const filteredOptions = computed(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) return props.options;
    return props.options.filter((option) => option.label.toLowerCase().includes(kw));
});

const handleSelect = (value: Status) => {
    emit("update:modelValue", value);
    emit("change", value);
    open.value = false;
    keyword.value = "";
};

const handleTriggerClick = (event: MouseEvent) => {
    emit("click", event);
};
</script>

<template>
    <PopoverSelect
        v-model:open="open"
        v-model:keyword="keyword"
        :disabled="disabled"
        :placeholder="placeholder"
        :show-search="true"
        search-placeholder="搜索..."
        :dropdown-width="240"
        :dropdown-max-height="220"
        :bordered="false"
    >
        <template #trigger="{ open: triggerOpen }">
            <slot>
                <div class="status-cell-trigger" :class="{ 'is-disabled': disabled }" @click="handleTriggerClick">
                    <span class="status-badge" :class="[statusClassMap[modelValue] || '', { 'is-open': triggerOpen }]">
                        {{ modelValue || placeholder }}
                    </span>
                </div>
            </slot>
        </template>

        <div class="status-picker-content">
            <div
                v-for="opt in filteredOptions"
                :key="opt.value"
                class="status-filter-row"
                :class="{ 'is-active': modelValue === opt.value, 'is-disabled': disabled }"
                @click.stop="!disabled && handleSelect(opt.value)"
            >
                <div class="status-filter-row-left">
                    <vort-checkbox
                        :checked="modelValue === opt.value"
                        @click.stop
                        @update:checked="!disabled && handleSelect(opt.value)"
                    />
                    <span class="text-sm text-gray-700 leading-5">{{ opt.label }}</span>
                </div>
            </div>
        </div>
    </PopoverSelect>
</template>

<style scoped>
.status-cell-trigger {
    padding: 2px 8px;
    cursor: pointer;
}

.status-cell-trigger.is-disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

.status-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    border: 1px solid;
}

.status-picker-content {
    padding: 8px 8px 4px;
}

.status-filter-row {
    min-height: 32px;
    padding: 2px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s ease;
}

.status-filter-row:hover {
    background: rgba(0, 0, 0, 0.04);
}

.status-filter-row.is-active {
    background: #f1f5f9;
}

.status-filter-row.is-disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

.status-filter-row-left {
    display: flex;
    align-items: center;
    gap: 12px;
}
</style>

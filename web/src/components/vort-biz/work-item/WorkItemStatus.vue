<script setup lang="ts">
import { computed } from "vue";
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
}>();

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

const open = defineModel<boolean>("open", { default: false });
const keyword = defineModel<string>("keyword", { default: "" });

const filteredOptions = computed(() => {
    const kw = keyword.value.trim();
    if (!kw) return props.options;
    return props.options.filter((x) => x.label.includes(kw));
});

const handleSelect = (value: Status) => {
    emit("update:modelValue", value);
    emit("change", value);
    open.value = false;
    keyword.value = "";
};
</script>

<template>
    <vort-popover
        v-model:open="open"
        trigger="click"
        placement="bottomLeft"
        :arrow="false"
        :disabled="disabled"
    >
        <slot>
            <vort-button
                class="h-8 min-w-[130px] px-3 border border-slate-300 rounded-md bg-white hover:border-slate-400 font-normal"
                :class="{ 'border-blue-500 ring-1 ring-blue-200': open }"
                :disabled="disabled"
            >
                <span class="status-badge" :class="statusClassMap[modelValue] || ''">
                    {{ modelValue || placeholder }}
                </span>
            </vort-button>
        </slot>
        <template #content>
            <div class="w-[240px] p-3" @click.stop>
                <div class="mb-2">
                    <vort-input v-model="keyword" placeholder="搜索..." class="w-full" size="small" />
                </div>
                <div class="max-h-[220px] overflow-y-auto pr-1">
                    <vort-button
                        v-for="opt in filteredOptions"
                        :key="opt.value"
                        class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                        variant="text"
                        :class="{ 'bg-slate-100': modelValue === opt.value }"
                        :disabled="disabled"
                        @click.stop="handleSelect(opt.value)"
                    >
                        <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                            <span v-if="modelValue === opt.value">✓</span>
                        </span>
                        <span class="text-sm text-gray-700">{{ opt.label }}</span>
                    </vort-button>
                </div>
            </div>
        </template>
    </vort-popover>
</template>

<style scoped>
.status-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    border: 1px solid;
}
</style>

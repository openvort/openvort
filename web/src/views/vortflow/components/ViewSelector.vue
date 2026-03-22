<script setup lang="ts">
import { computed, ref } from "vue";
import { ChevronDown, Check, Plus, Settings, PinOff } from "lucide-vue-next";
import PopoverSelect from "@/components/vort-biz/popover-select/PopoverSelect.vue";
import type { VortFlowView } from "../composables/useVortFlowViews";

interface Props {
    views: VortFlowView[];
    selectedId: string;
    totalCount?: number;
}

const props = withDefaults(defineProps<Props>(), {
    totalCount: 0,
});

const emit = defineEmits<{
    "update:selectedId": [value: string];
    createView: [];
    manageViews: [];
    pinSidebar: [];
}>();

const dropdownOpen = ref(false);
const searchKeyword = ref("");

const selectedView = computed(() =>
    props.views.find(v => v.id === props.selectedId) ?? props.views[0]
);

const filteredViews = computed(() => {
    const kw = searchKeyword.value.trim().toLowerCase();
    if (!kw) return props.views;
    return props.views.filter(v => v.name.toLowerCase().includes(kw));
});

const selectView = (id: string) => {
    emit("update:selectedId", id);
    dropdownOpen.value = false;
};

const scopeLabel = (scope: string) => {
    if (scope === "shared") return "公共";
    if (scope === "personal") return "个人";
    return "系统";
};
</script>

<template>
    <PopoverSelect
        v-model:open="dropdownOpen"
        v-model:keyword="searchKeyword"
        :show-search="true"
        search-placeholder="请输入视图名称"
        :dropdown-width="280"
        :dropdown-max-height="400"
        :bordered="false"
        placement="bottomLeft"
    >
        <template #trigger>
            <button
                type="button"
                class="view-trigger"
                :class="{ 'is-open': dropdownOpen }"
                @click.stop="dropdownOpen = !dropdownOpen"
            >
                <span class="view-name">{{ selectedView?.name || '全部工作项' }}</span>
                <ChevronDown
                    :size="14"
                    class="text-gray-400 shrink-0 transition-transform duration-200"
                    :class="{ 'rotate-180': dropdownOpen }"
                />
            </button>
        </template>

        <div class="py-1">
            <div class="px-3 py-1.5 text-xs text-gray-400 font-medium">视图</div>

            <div
                v-for="view in filteredViews"
                :key="view.id"
                class="view-row"
                :class="{ 'is-active': props.selectedId === view.id }"
                @click.stop="selectView(view.id)"
            >
                <div class="flex items-center gap-2 min-w-0 flex-1">
                    <Check
                        v-if="props.selectedId === view.id"
                        :size="14"
                        class="text-blue-500 shrink-0"
                    />
                    <span v-else class="w-3.5 shrink-0" />
                    <span class="text-sm text-gray-700 truncate">{{ view.name }}</span>
                </div>
                <span class="text-xs text-gray-400 shrink-0">{{ scopeLabel(view.scope) }}</span>
            </div>

            <div v-if="!filteredViews.length" class="px-4 py-4 text-center text-sm text-gray-400">
                未找到匹配的视图
            </div>
        </div>

        <template #footer>
            <div class="py-1">
                <button type="button" class="footer-action" @click="dropdownOpen = false; emit('createView')">
                    <Plus :size="14" class="text-gray-400" />
                    <span>新建视图</span>
                </button>
                <button type="button" class="footer-action" @click="dropdownOpen = false; emit('manageViews')">
                    <Settings :size="14" class="text-gray-400" />
                    <span>视图管理</span>
                </button>
                <div class="border-t border-gray-100 my-1" />
                <button type="button" class="footer-action" @click="dropdownOpen = false; emit('pinSidebar')">
                    <PinOff :size="14" class="text-gray-400" />
                    <span>将视图固定在左侧</span>
                </button>
            </div>
        </template>
    </PopoverSelect>
</template>

<style scoped>
.view-trigger {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px;
    border-radius: 6px;
    border: none;
    background: transparent;
    cursor: pointer;
    transition: background 0.2s;
    font-size: 14px;
    white-space: nowrap;
}

.view-trigger:hover,
.view-trigger.is-open {
    background: rgba(0, 0, 0, 0.04);
}

.view-name {
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    font-weight: 500;
}

.view-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 6px 12px;
    margin: 0 4px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s ease;
}

.view-row:hover {
    background: rgba(0, 0, 0, 0.04);
}

.view-row.is-active {
    background: #f1f5f9;
}

.footer-action {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    margin: 0 4px;
    border: none;
    background: transparent;
    border-radius: 6px;
    font-size: 13px;
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
    cursor: pointer;
    transition: background 0.15s;
    text-align: left;
    box-sizing: border-box;
    width: calc(100% - 8px);
}
.footer-action:hover {
    background: rgba(0, 0, 0, 0.04);
}
</style>

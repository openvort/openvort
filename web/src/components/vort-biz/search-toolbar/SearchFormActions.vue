<script setup lang="ts">
/**
 * SearchFormActions - 搜索表单操作按钮组件
 *
 * 封装搜索和重置按钮，提供统一的样式和行为
 * 会自动从 SearchToolbar 注入 onSearch 和 onReset，也可以通过事件覆盖
 *
 * @example 配合 SearchToolbar 使用（推荐，自动绑定）
 * <SearchToolbar :on-search="onSearchSubmit" :on-reset="resetParams">
 *   <SearchForm>
 *     <SearchFormActions />
 *   </SearchForm>
 * </SearchToolbar>
 *
 * @example 单独使用（手动绑定事件）
 * <SearchFormActions @search="onSearch" @reset="onReset" />
 *
 * @example 自定义按钮文本
 * <SearchFormActions search-text="查询" reset-text="清空" />
 *
 * @example 隐藏重置按钮
 * <SearchFormActions :show-reset="false" />
 */
import { inject, computed } from "vue";
import { SEARCH_TOOLBAR_KEY, type SearchToolbarContext } from "./types";
import { SEARCH_FORM_CONTEXT_KEY, type SearchFormContext } from "./context";

defineOptions({
    name: "SearchFormActions"
});

interface Props {
    /** 搜索按钮文本 */
    searchText?: string;
    /** 重置按钮文本 */
    resetText?: string;
    /** 是否显示重置按钮 */
    showReset?: boolean;
    /** 搜索按钮加载状态（优先级高于 SearchToolbar 注入的值） */
    loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    searchText: "搜索",
    resetText: "重置",
    showReset: true,
    loading: undefined
});

const emit = defineEmits<{
    /** 点击搜索按钮 */
    search: [];
    /** 点击重置按钮 */
    reset: [];
}>();

// 从 SearchToolbar 注入
const toolbarContext = inject<SearchToolbarContext>(SEARCH_TOOLBAR_KEY, {});

// 从 SearchForm 注入 labelWidth
const searchFormContext = inject<SearchFormContext | undefined>(SEARCH_FORM_CONTEXT_KEY, undefined);

// 默认 labelWidth
const DEFAULT_LABEL_WIDTH = 78;

// loading 状态：props 优先，否则用注入的值
const isLoading = computed(() => {
    if (props.loading !== undefined) return props.loading;
    return toolbarContext.loading?.value ?? false;
});

// 计算 padding-left 样式（使用 CSS 变量，便于移动端覆盖）
const actionsStyle = computed(() => {
    const width = searchFormContext?.labelWidth?.value ?? DEFAULT_LABEL_WIDTH;
    const paddingLeft = typeof width === "number" ? `${width}px` : width;
    return { "--actions-padding-left": paddingLeft } as Record<string, string>;
});

const handleSearch = () => {
    // 先触发事件，如果有监听器会处理
    emit("search");
    // 如果有注入的 onSearch，也调用
    toolbarContext.onSearch?.();
};

const handleReset = () => {
    emit("reset");
    toolbarContext.onReset?.();
};
</script>

<template>
    <div class="search-form-actions" :style="actionsStyle">
        <vort-button variant="plain" :loading="isLoading" @click="handleSearch">
            {{ searchText }}
        </vort-button>
        <vort-button v-if="showReset" variant="default" @click="handleReset">
            {{ resetText }}
        </vort-button>
        <slot />
    </div>
</template>

<style lang="less" scoped>
.search-form-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    // 默认单独占一行
    flex-basis: 100%;
    padding-top: 4px;
    // padding-left 通过 CSS 变量设置（与 SearchFormItem 的 label 对齐）
    padding-left: var(--actions-padding-left, 78px);
}

@media only screen and (max-width: 767px) {
    .search-form-actions {
        flex-direction: column;
        align-items: stretch;
        padding-left: 0;

        :deep(button) {
            width: 100%;
        }
    }
}
</style>

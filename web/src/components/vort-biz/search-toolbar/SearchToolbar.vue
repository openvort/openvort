<script setup lang="ts">
/**
 * SearchToolbar - 搜索工具栏容器组件
 *
 * 用于列表页面的搜索区域外层容器，包含搜索表单和操作按钮区域
 *
 * @example 基础用法（传入 onSearch 和 onReset，SearchFormActions 会自动绑定）
 * <SearchToolbar :on-search="onSearchSubmit" :on-reset="resetParams">
 *   <SearchForm>
 *     <SearchFormItem label="关键词">
 *       <vort-input v-model="keyword" />
 *     </SearchFormItem>
 *     <SearchFormActions />
 *   </SearchForm>
 *   <template #actions>
 *     <el-button type="primary">新增</el-button>
 *   </template>
 * </SearchToolbar>
 *
 * @example 也可以在 SearchFormActions 上单独绑定
 * <SearchToolbar>
 *   <SearchForm>
 *     <SearchFormActions @search="onSearch" @reset="onReset" />
 *   </SearchForm>
 * </SearchToolbar>
 */
import { useSlots, provide, toRef } from "vue";
import { SEARCH_TOOLBAR_KEY } from "./types";

defineOptions({
    name: "SearchToolbar"
});

interface Props {
    /** 搜索回调函数 */
    onSearch?: () => void;
    /** 重置回调函数 */
    onReset?: () => void;
    /** 搜索按钮加载状态 */
    loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    onSearch: undefined,
    onReset: undefined,
    loading: false
});

const slots = useSlots();

// 提供给子组件
provide(SEARCH_TOOLBAR_KEY, {
    onSearch: props.onSearch,
    onReset: props.onReset,
    loading: toRef(props, "loading")
});
</script>

<template>
    <div class="search-toolbar">
        <div class="search-toolbar__search">
            <slot />
        </div>
        <div v-if="slots.actions" class="search-toolbar__actions">
            <slot name="actions" />
        </div>
    </div>
</template>

<style lang="less" scoped>
.search-toolbar {
    display: flex;
    flex-direction: column;
    gap: 16px;

    &__search {
        background-color: #f5f7fa;
        border: 1px solid #f0f2f5;
        padding: 12px 20px;
        border-radius: var(--vort-border-radius, 8px);
    }

    &__actions {
        display: flex;
        align-items: center;
    }
}
</style>

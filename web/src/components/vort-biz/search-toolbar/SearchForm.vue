<script setup lang="ts">
/**
 * SearchForm - 搜索表单容器组件
 *
 * 基于 vort-form 封装，使用 inline 布局，适用于列表页搜索区域
 *
 * @example
 * <SearchForm>
 *   <SearchFormItem label="关键词">
 *     <vort-input v-model="keyword" />
 *   </SearchFormItem>
 *   <SearchFormItem label="状态">
 *     <el-select v-model="status" />
 *   </SearchFormItem>
 *   <SearchFormActions @search="onSearch" @reset="onReset" />
 * </SearchForm>
 *
 * @example 统一设置 label 宽度
 * <SearchForm label-width="100px">
 *   <SearchFormItem label="关键词">...</SearchFormItem>
 *   <SearchFormItem label="状态">...</SearchFormItem>
 * </SearchForm>
 *
 * @example 使用 vort-form 的验证功能
 * <SearchForm :model="formData" :rules="schema">
 *   ...
 * </SearchForm>
 */
import { provide, toRef } from "vue";
import type { ZodType } from "zod";
import { SEARCH_FORM_CONTEXT_KEY } from "./context";

defineOptions({
    name: "SearchForm"
});

interface Props {
    /** 表单数据对象（可选，用于验证） */
    model?: Record<string, unknown>;
    /** 表单验证规则（可选，支持 zod schema） */
    rules?: ZodType | Record<string, unknown>;
    /** 统一设置所有 SearchFormItem 的 label 宽度 */
    labelWidth?: string | number;
}

const props = withDefaults(defineProps<Props>(), {
    model: undefined,
    rules: undefined,
    labelWidth: undefined
});

// 向子组件提供 labelWidth
provide(SEARCH_FORM_CONTEXT_KEY, {
    labelWidth: toRef(props, "labelWidth")
});
</script>

<template>
    <vort-form class="search-form" layout="inline" :model="model" :rules="rules" :colon="false">
        <slot />
    </vort-form>
</template>

<style lang="less" scoped>
.search-form {
    :deep(.vort-form-item) {
        margin-bottom: 0;
    }
}

@media only screen and (max-width: 767px) {
    .search-form {
        flex-direction: column;
        align-items: stretch;
        gap: 10px;
    }
}
</style>

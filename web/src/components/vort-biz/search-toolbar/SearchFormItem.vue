<script setup lang="ts">
/**
 * SearchFormItem - 搜索表单项组件
 *
 * 用于包裹单个搜索控件，提供统一的 label + 控件布局
 *
 * @example
 * <SearchFormItem label="商品名称">
 *   <vort-input v-model="name" placeholder="请输入" />
 * </SearchFormItem>
 *
 * @example 无 label（用于搜索/重置按钮区域）
 * <SearchFormItem>
 *   <el-button type="primary">搜索</el-button>
 *   <el-button>重置</el-button>
 * </SearchFormItem>
 */
import { computed, inject } from "vue";
import { SEARCH_FORM_CONTEXT_KEY, type SearchFormContext } from "./context";

defineOptions({
    name: "SearchFormItem"
});

interface Props {
    /** 标签文本 */
    label?: string;
    /** 标签宽度，默认 78px（优先级高于 SearchForm 的 labelWidth） */
    labelWidth?: string | number;
    /** 控件容器宽度，默认 270px */
    controlWidth?: string | number;
}

const props = withDefaults(defineProps<Props>(), {
    label: "",
    labelWidth: undefined,
    controlWidth: 270
});

// 从父组件 SearchForm 注入 labelWidth
const searchFormContext = inject<SearchFormContext | undefined>(SEARCH_FORM_CONTEXT_KEY, undefined);

// 默认 labelWidth
const DEFAULT_LABEL_WIDTH = 78;

const labelStyle = computed(() => {
    // 优先级：props.labelWidth > searchFormContext.labelWidth > 默认值
    const width = props.labelWidth ?? searchFormContext?.labelWidth?.value ?? DEFAULT_LABEL_WIDTH;
    const widthStr = typeof width === "number" ? `${width}px` : width;
    return { width: widthStr };
});

const controlStyle = computed(() => {
    const width = typeof props.controlWidth === "number" ? `${props.controlWidth}px` : props.controlWidth;
    return { width };
});
</script>

<template>
    <div class="search-form-item">
        <div class="search-form-item__group">
            <label v-if="label" class="search-form-item__label" :style="labelStyle">
                <span>{{ label }}：</span>
            </label>
            <div class="search-form-item__control" :style="controlStyle">
                <slot />
            </div>
        </div>
    </div>
</template>

<style lang="less" scoped>
.search-form-item {
    display: flex;
    align-items: center;

    &__group {
        width: 100%;
        display: flex;
        align-items: baseline;
    }

    &__label {
        color: #333;
        padding: 0;
        text-align: right;
        white-space: nowrap;
        line-height: 24px;
        width: auto;
        padding-right: 3px;
        flex-shrink: 0;
    }

    &__control {
        box-sizing: border-box;
        width: 270px;
        position: relative;
        min-height: 1px;
        flex: 1;
    }
}

@media only screen and (max-width: 767px) {
    .search-form-item {
        width: 100%;

        :deep(.el-button--primary) {
            width: 100%;
            margin-bottom: 10px;
        }

        :deep(.el-button.is-plain) {
            width: 100%;
            margin-left: 0px;
        }
    }
}
</style>

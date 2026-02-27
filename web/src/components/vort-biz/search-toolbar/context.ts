import type { InjectionKey, Ref } from "vue";

/**
 * SearchForm 上下文类型
 */
export interface SearchFormContext {
    /** 统一的 label 宽度 */
    labelWidth: Ref<string | number | undefined>;
}

/**
 * SearchForm 上下文注入 key
 */
export const SEARCH_FORM_CONTEXT_KEY: InjectionKey<SearchFormContext> = Symbol("SearchFormContext");

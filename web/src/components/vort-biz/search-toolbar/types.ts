import type { InjectionKey, Ref } from "vue";

// SearchToolbar 注入的上下文类型
export interface SearchToolbarContext {
    onSearch?: () => void;
    onReset?: () => void;
    loading?: Ref<boolean>;
}

// 注入 key
export const SEARCH_TOOLBAR_KEY: InjectionKey<SearchToolbarContext> = Symbol("SearchToolbar");

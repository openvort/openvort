import type { InjectionKey } from "vue";

/**
 * Row 组件上下文接口
 */
export interface RowContext {
    gutter: [number, number];
}

/**
 * Row 组件上下文注入 Key
 */
export const rowContextKey: InjectionKey<RowContext> = Symbol("rowContext");

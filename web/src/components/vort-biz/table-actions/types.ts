import type { InjectionKey } from "vue";

/**
 * 操作项样式类型
 * - text: 链接文字样式（默认）
 * - button: 按钮样式（vort-button type=text）
 */
export type TableActionsType = "text" | "button";

/**
 * TableActions 组件的上下文，通过 provide/inject 传递给子组件
 */
export interface TableActionsContext {
    /** 样式类型 */
    type: TableActionsType;
    /** 是否显示分隔线 */
    divider: boolean;
}

/**
 * TableActions 上下文的 injection key
 */
export const TABLE_ACTIONS_KEY: InjectionKey<TableActionsContext> = Symbol("TableActionsContext");

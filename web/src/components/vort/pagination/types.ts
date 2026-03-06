/**
 * Pagination 分页组件类型定义
 */

/** 分页器尺寸 */
export type PaginationSize = "default" | "small";

/** Pagination 组件 Props */
export interface PaginationProps {
    /** 当前页数 (v-model:current) */
    current?: number;
    /** 每页条数 (v-model:pageSize) */
    pageSize?: number;
    /** 数据总数 */
    total?: number;
    /** 是否禁用 */
    disabled?: boolean;
    /** 只有一页时是否隐藏分页器 */
    hideOnSinglePage?: boolean;
    /** 用于显示数据总量和当前数据顺序（函数形式，自定义格式） */
    showTotal?: (total: number, range: [number, number]) => string;
    /** 是否显示总数信息，格式：第1-15 条 / 总共 3989 条 */
    showTotalInfo?: boolean;
    /** 是否显示 pageSize 切换器 */
    showSizeChanger?: boolean;
    /** 指定每页可以显示多少条 */
    pageSizeOptions?: number[];
    /** 是否显示快速跳转 */
    showQuickJumper?: boolean;
    /** 当前页面展示的最大页码按钮数 */
    showLessItems?: boolean;
    /** 简洁版本 */
    simple?: boolean;
    /** 尺寸 */
    size?: PaginationSize;
    /** 自定义类名 */
    class?: string;
}

/** Pagination 组件 Emits */
export interface PaginationEmits {
    /** 当前页改变时触发 */
    (e: "update:current", page: number): void;
    /** 每页条数改变时触发 */
    (e: "update:pageSize", size: number): void;
    /** 页码或每页条数改变时触发 */
    (e: "change", page: number, pageSize: number): void;
    /** 每页条数改变时触发 */
    (e: "showSizeChange", current: number, size: number): void;
}

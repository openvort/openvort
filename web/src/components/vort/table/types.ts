/**
 * Table 组件类型定义
 */

import type { VNode } from "vue";

export interface TableColumn<T = any> {
    /** 列唯一标识（用于 key） */
    key?: string;
    /** 列数据字段名 */
    dataIndex?: string;
    /** 列标题 */
    title?: string;
    /** 列宽度 */
    width?: number | string;
    /** 列对齐方式 */
    align?: "left" | "center" | "right";
    /** 是否固定列 */
    fixed?: "left" | "right";
    /** 自定义渲染内容（插槽名称，用于 columns prop 方式） */
    slot?: string;
    /** 自定义单元格样式类名 */
    className?: string;
    /** 自定义表头样式类名 */
    headerClassName?: string;
    /** 是否可排序 (true: 前端排序, "custom": 后端排序, function: 自定义排序函数) */
    sorter?: boolean | "custom" | ((a: T, b: T) => number);
    /** 排序顺序 */
    sortOrder?: "ascend" | "descend" | null;
    /** 默认排序顺序 */
    defaultSortOrder?: "ascend" | "descend";
    /** 是否省略超长内容 */
    ellipsis?: boolean;
    /** 子列配置（用于多级表头） */
    children?: TableColumn<T>[];
    /** 内部使用：TableColumn 组件的唯一 ID */
    _uid?: string;
    /** 内部使用：TableColumn 组件的默认插槽渲染函数 */
    _renderCell?: (scope: TableCellScope<T>) => VNode[];
    /** 内部使用：TableColumn 组件的表头插槽渲染函数 */
    _renderHeader?: (scope: TableHeaderScope<T>) => VNode[];
}

/** 单元格插槽作用域 */
export interface TableCellScope<T = any> {
    /** 单元格值 */
    value: any;
    /** 当前行数据 */
    row: T;
    /** 当前行索引 */
    index: number;
    /** 列配置 */
    column: TableColumn<T>;
}

/** 表头插槽作用域 */
export interface TableHeaderScope<T = any> {
    /** 列配置 */
    column: TableColumn<T>;
}

/** Table 组件注入的上下文 */
export interface TableContext<T = any> {
    /** 注册列 */
    registerColumn: (column: TableColumn<T>) => void;
    /** 注销列 */
    unregisterColumn: (uid: string) => void;
}

/** Table 注入 key */
export const TABLE_INJECTION_KEY = Symbol("VortTable") as InjectionKey<TableContext>;

/** TableColumn 父子嵌套注入的上下文 */
export interface TableColumnContext<T = any> {
    /** 注册子列 */
    registerChildColumn: (column: TableColumn<T>) => void;
    /** 注销子列 */
    unregisterChildColumn: (uid: string) => void;
}

/** TableColumn 注入 key */
export const TABLE_COLUMN_INJECTION_KEY = Symbol("VortTableColumn") as InjectionKey<TableColumnContext>;

import type { InjectionKey } from "vue";

export interface TablePagination {
    /** 当前页码 */
    current?: number;
    /** 每页条数 */
    pageSize?: number;
    /** 总条数 */
    total?: number;
    /** 是否显示分页 */
    showPagination?: boolean;
    /** 每页条数选项 */
    pageSizeOptions?: number[];
    /** 是否显示快速跳转 */
    showQuickJumper?: boolean;
    /** 是否显示每页条数切换 */
    showSizeChanger?: boolean;
    /** 是否显示总数 */
    showTotal?: boolean | ((total: number, range: [number, number]) => string);
}

export interface TableRowSelection<T = any> {
    /** 选中项的 key 数组 */
    selectedRowKeys?: (string | number)[];
    /** 选择类型 */
    type?: "checkbox" | "radio";
    /** 选择回调 */
    onChange?: (selectedRowKeys: (string | number)[], selectedRows: T[]) => void;
    /** 是否固定选择列 */
    fixed?: boolean;
    /** 选择列宽度 */
    columnWidth?: number | string;
    /** 是否隐藏全选 */
    hideSelectAll?: boolean;
    /** 自定义选择项（全选/反选等） */
    selections?: boolean;
    /** 用户手动选择/取消选择某行的回调 */
    onSelect?: (record: T, selected: boolean, selectedRows: T[]) => void;
    /** 用户手动选择/取消选择所有行的回调 */
    onSelectAll?: (selected: boolean, selectedRows: T[], changeRows: T[]) => void;
    /** 获取 Checkbox 的默认属性 */
    getCheckboxProps?: (record: T) => { disabled?: boolean; name?: string };
}

export interface TableScroll {
    /** 横向滚动宽度 */
    x?: number | string;
    /** 纵向滚动高度 */
    y?: number | string;
}

export type TableSize = "large" | "middle" | "small";

/** 排序状态 */
export interface SortState {
    /** 排序字段 */
    field: string;
    /** 排序顺序 */
    order: "ascend" | "descend" | null;
}

/** 树形表格配置 */
export interface TableTreeProps {
    /** 子节点字段名，默认 'children' */
    children?: string;
    /** 是否有子节点的字段名，默认 'hasChildren' */
    hasChildren?: string;
}

/** 树形节点状态 */
export interface TreeNodeState {
    /** 是否展开 */
    expanded: boolean;
    /** 是否正在加载 */
    loading: boolean;
    /** 是否已加载过 */
    loaded: boolean;
    /** 节点层级 */
    level: number;
}

/** 加载子节点的回调函数类型 */
export type LoadChildrenFn<T = any> = (row: T) => Promise<T[]>;

/** 虚拟滚动配置 */
export interface TableVirtualConfig {
    /** 是否启用虚拟滚动 */
    enabled?: boolean;
    /** 行高估算值（像素） */
    rowHeight?: number;
    /** 过扫描行数 */
    overscan?: number;
}

/** Table 组件 Props 类型（完整） */
export interface TableProps<T = any> {
    columns?: TableColumn<T>[];
    dataSource?: T[];
    rowKey?: string | ((record: T) => string | number);
    bordered?: boolean;
    size?: TableSize;
    loading?: boolean;
    pagination?: TablePagination | false;
    rowSelection?: TableRowSelection<T>;
    scroll?: TableScroll;
    minHeight?: number | string;
    maxHeight?: number | string;
    emptyText?: string;
    showHeader?: boolean;
    stripe?: boolean;
    rowClassName?: string | ((record: T, index: number) => string);
    class?: string;
    treeProps?: TableTreeProps;
    loadChildren?: LoadChildrenFn<T>;
    defaultExpandedRowKeys?: (string | number)[];
    expandedRowKeys?: (string | number)[];
    expandRowByClick?: boolean;
    indent?: number;
    showExpandLoading?: boolean;
    /** 是否启用虚拟滚动 */
    virtual?: boolean;
    /** 虚拟滚动行高 */
    virtualRowHeight?: number;
    /** 虚拟滚动过扫描行数 */
    virtualOverscan?: number;
}

/** Table 组件 Emits 类型 */
export interface TableEmits<T = any> {
    change: [pagination: { current: number; pageSize: number }, filters: Record<string, any>, sorter: { field: string; order: "ascend" | "descend" | null }];
    expand: [expanded: boolean, record: T];
    "update:expandedRowKeys": [keys: (string | number)[]];
    "update:selectedRowKeys": [keys: (string | number)[]];
}

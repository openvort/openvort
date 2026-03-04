/**
 * ProTable 组件类型定义
 * 独立开发的业务增强表格组件
 */

import type { VNode, Ref } from "vue";

/** 表格列配置 */
export interface TableColumn<T = any> {
  /** 列唯一标识 */
  key?: string;
  /** 数据字段名 */
  dataIndex?: string;
  /** 列标题 */
  title?: string;
  /** 列宽度 */
  width?: number | string;
  /** 对齐方式 */
  align?: "left" | "center" | "right";
  /** 固定列 */
  fixed?: "left" | "right";
  /** 单元格样式类名 */
  className?: string;
  /** 表头样式类名 */
  headerClassName?: string;
  /** 是否可排序 */
  sorter?: boolean | "custom" | ((a: T, b: T) => number);
  /** 排序顺序 */
  sortOrder?: "ascend" | "descend" | null;
  /** 默认排序 */
  defaultSortOrder?: "ascend" | "descend";
  /** 省略超长内容 */
  ellipsis?: boolean;
  /** 子列（多级表头） */
  children?: TableColumn<T>[];
  /** 插槽名称 */
  slot?: string;
  /** 插槽渲染函数 */
  _renderCell?: (scope: TableCellScope<T>) => VNode[];
  /** 表头渲染函数 */
  _renderHeader?: (scope: TableHeaderScope<T>) => VNode[];
  /** 内部使用 */
  _uid?: string;
}

/** 单元格作用域 */
export interface TableCellScope<T = any> {
  value: any;
  row: T;
  index: number;
  column: TableColumn<T>;
}

/** 表头作用域 */
export interface TableHeaderScope<T = any> {
  column: TableColumn<T>;
}

/** 分页配置 */
export interface TablePagination {
  current?: number;
  pageSize?: number;
  total?: number;
  showPagination?: boolean;
  pageSizeOptions?: number[];
  showQuickJumper?: boolean;
  showSizeChanger?: boolean;
  showTotal?: boolean | ((total: number, range: [number, number]) => string);
}

/** 行选择配置 */
export interface TableRowSelection<T = any> {
  selectedRowKeys?: (string | number)[];
  type?: "checkbox" | "radio";
  onChange?: (selectedRowKeys: (string | number)[], selectedRows: T[]) => void;
  fixed?: boolean;
  columnWidth?: number | string;
  hideSelectAll?: boolean;
  onSelect?: (record: T, selected: boolean, selectedRows: T[]) => void;
  onSelectAll?: (selected: boolean, selectedRows: T[], changeRows: T[]) => void;
  getCheckboxProps?: (record: T) => { disabled?: boolean; name?: string };
}

/** 滚动配置 */
export interface TableScroll {
  x?: number | string;
  y?: number | string;
}

/** 表格尺寸 */
export type TableSize = "large" | "middle" | "small";

/** 排序状态 */
export interface SortState {
  field: string;
  order: "ascend" | "descend" | null;
}

// ==================== ProTable 扩展类型 ====================

/** 工具栏配置 */
export interface ProTableToolbar {
  refresh?: boolean;
  columnSetting?: boolean;
  density?: boolean;
  fullscreen?: boolean;
}

/** 列设置项 */
export interface ColumnSettingItem {
  key: string;
  title: string;
  visible?: boolean;
  draggable?: boolean;
  disabled?: boolean;
  width?: number;
}

/** 快捷筛选 */
export interface QuickFilter {
  field: string;
  label: string;
  value?: any;
  active?: boolean;
}

/** ProTable 列扩展 */
export interface ProTableColumn<T = any> extends TableColumn<T> {
  defaultShow?: boolean;
  searchable?: boolean;
  searchConfig?: {
    type: "input" | "select" | "date" | "daterange";
    placeholder?: string;
    options?: { label: string; value: any }[];
  };
}

/** ProTable 分页 */
export interface ProTablePagination extends TablePagination {
  defaultPageSize?: number;
  hideOnSinglePage?: boolean;
}

/** 请求参数 */
export interface ProTableRequestParams {
  current: number;
  pageSize: number;
  sortField?: string;
  sortOrder?: "ascend" | "descend";
  filters?: Record<string, any>;
  [key: string]: any;
}

/** 请求响应 */
export interface ProTableResponse<T = any> {
  data: T[];
  total: number;
  current: number;
  pageSize: number;
}

/** ProTable Props */
export interface ProTableProps<T = any> {
  columns?: ProTableColumn<T>[];
  dataSource?: T[];
  request?: (params: ProTableRequestParams) => Promise<ProTableResponse<T>>;
  params?: Record<string, any>;
  rowKey?: string | ((record: T) => string | number);
  bordered?: boolean;
  size?: TableSize;
  loading?: boolean;
  pagination?: ProTablePagination | false;
  rowSelection?: TableRowSelection<T>;
  scroll?: TableScroll;
  toolbar?: ProTableToolbar | false;
  columnSettingPersistence?: boolean;
  columnSettingKey?: string;
  quickFilters?: QuickFilter[];
}

/** ProTable Emits */
export interface ProTableEmits<T = any> {
  requestChange: [params: ProTableRequestParams];
  paginationChange: [pagination: { current: number; pageSize: number }];
  sortChange: [sorter: { field: string; order: "ascend" | "descend" | null }];
  filterChange: [filters: Record<string, any>];
  selectionChange: [selectedRowKeys: (string | number)[], selectedRows: T[]];
  refresh: [];
}

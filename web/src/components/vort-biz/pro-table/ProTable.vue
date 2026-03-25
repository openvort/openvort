<script setup lang="ts" generic="T = any">
import { ref, computed, watch, onBeforeUnmount, onMounted, nextTick } from "vue";
import { Checkbox, Spin, Pagination, Popover } from "@/components/vort";
import { CaretUpFilled, CaretDownFilled, EmptyOutlined } from "@/components/vort/icons";
import type {
  TableColumn,
  TablePagination,
  TableRowSelection,
  TableScroll,
  TableSize,
  SortState,
  ProTableColumn,
  ProTableRequestParams,
  ProTableResponse
} from "./types";

defineOptions({ name: "VortProTable" });

interface Props<T = any> {
  columns?: ProTableColumn<T>[];
  dataSource?: T[];
  postProcessData?: (rows: T[]) => T[];
  request?: (params: ProTableRequestParams) => Promise<ProTableResponse<T>>;
  params?: Record<string, any>;
  rowKey?: string | ((record: T) => string | number);
  bordered?: boolean;
  size?: TableSize;
  cellPadding?: "none" | number;
  loading?: boolean;
  pagination?: TablePagination | false;
  rowSelection?: TableRowSelection<T>;
  scroll?: TableScroll;
  toolbar?: any;
}

const props = withDefaults(defineProps<Props<T>>(), {
  columns: () => [],
  dataSource: () => [],
  postProcessData: undefined,
  params: () => ({}),
  rowKey: "id",
  bordered: false,
  size: "middle",
  cellPadding: "none",
  loading: false,
  pagination: () => ({ current: 1, pageSize: 20, total: 0, showPagination: true }),
  toolbar: () => ({ refresh: true, columnSetting: true })
});

const emit = defineEmits<{
  requestChange: [params: ProTableRequestParams];
  paginationChange: [pagination: { current: number; pageSize: number }];
  sortChange: [sorter: { field: string; order: "ascend" | "descend" | null }];
  filterChange: [filters: Record<string, any>];
  selectionChange: [selectedRowKeys: (string | number)[], selectedRows: T[]];
  columnWidthChange: [widths: Record<string, number>];
  refresh: [];
}>();

// ==================== 数据状态 ====================
const internalDataSource = ref<T[]>([]);
const total = ref(0);
const current = ref(1);
const pageSize = ref(20);
const internalLoading = ref(false);

const requestParams = ref<ProTableRequestParams>({
  current: 1,
  pageSize: 20,
  ...props.params
});

const tableData = computed<T[]>(() => {
  const rows = props.request
    ? (internalDataSource.value as unknown as T[])
    : (props.dataSource as T[]);
  return props.postProcessData ? props.postProcessData(rows) : rows;
});

// ==================== 排序状态 ====================
const sortState = ref<SortState>({ field: "", order: null });

// ==================== 选择状态 ====================
const selectedRowKeys = ref<(string | number)[]>([]);

// ==================== 数据请求 ====================
const fetchData = async () => {
  if (!props.request) return;

  internalLoading.value = true;
  try {
    const result = await props.request({
      ...requestParams.value,
      current: current.value,
      pageSize: pageSize.value,
      sortField: sortState.value.field || undefined,
      sortOrder: sortState.value.order || undefined
    });
    internalDataSource.value = result.data || [];
    total.value = result.total || 0;
  } catch (error) {
    console.error("[ProTable] 请求失败:", error);
  } finally {
    internalLoading.value = false;
  }
};

// 监听外部 params 变化
watch(
  () => props.params,
  () => {
    requestParams.value = { ...requestParams.value, ...props.params };
    current.value = 1;
    fetchData();
  },
  { deep: true }
);

// 初始加载
if (props.request) {
  fetchData();
}

// ==================== 工具方法 ====================
const getRowKey = (record: T, index: number): string | number => {
  if (typeof props.rowKey === "function") {
    return props.rowKey(record);
  }
  return (record as any)[props.rowKey as string] ?? index;
};

const getCellValue = (record: T, column: TableColumn<T>): any => {
  if (!column.dataIndex) return "";
  const keys = column.dataIndex.split(".");
  let value: any = record;
  for (const key of keys) {
    value = value?.[key];
  }
  return value;
};

function getColumnKey(column: TableColumn<T>): string {
  return column.key || column.dataIndex || column.title || "";
}

// ==================== 列可见性（前向兼容） ====================
const isColumnVisible = (column: TableColumn<T>): boolean => {
  const col = column as TableColumn<T> & { defaultShow?: boolean; hideInTable?: boolean };
  if (typeof col.visible === "boolean") return col.visible;
  if (typeof col.defaultShow === "boolean") return col.defaultShow;
  if (typeof col.hideInTable === "boolean") return !col.hideInTable;
  return true;
};

const getVisibleColumnsTree = (columns: TableColumn<T>[]): TableColumn<T>[] => {
  const result: TableColumn<T>[] = [];
  for (const column of columns) {
    if (!isColumnVisible(column)) continue;
    if (hasChildren(column)) {
      const visibleChildren = getVisibleColumnsTree(column.children || []);
      if (visibleChildren.length === 0) continue;
      result.push({ ...column, children: visibleChildren });
    } else {
      result.push(column);
    }
  }
  return result;
};

const baseVisibleColumns = computed<TableColumn<T>[]>(() => getVisibleColumnsTree(props.columns || []));
const columnOrderKeys = ref<string[]>([]);

const syncColumnOrder = () => {
  const columns = baseVisibleColumns.value || [];
  const isSingleLevel = columns.every((column) => !Array.isArray(column.children) || column.children.length === 0);
  if (!isSingleLevel) {
    columnOrderKeys.value = [];
    return;
  }
  const latestKeys = columns.map((column) => getColumnKey(column)).filter(Boolean);
  columnOrderKeys.value = latestKeys;
};

watch(baseVisibleColumns, syncColumnOrder, { immediate: true, deep: true });

const visibleColumns = computed<TableColumn<T>[]>(() => {
  const columns = baseVisibleColumns.value || [];
  const isSingleLevel = columns.every((column) => !Array.isArray(column.children) || column.children.length === 0);
  if (!isSingleLevel) return columns;
  if (!columnOrderKeys.value.length) return columns;

  const columnMap = new Map(columns.map((column) => [getColumnKey(column), column] as const));
  const ordered: TableColumn<T>[] = [];

  for (const key of columnOrderKeys.value) {
    const column = columnMap.get(key);
    if (!column) continue;
    ordered.push(column);
    columnMap.delete(key);
  }

  for (const column of columns) {
    const key = getColumnKey(column);
    if (columnMap.has(key)) ordered.push(column);
  }
  return ordered;
});

// ==================== 多级表头支持 ====================
function hasChildren(column: TableColumn<T>): boolean {
  return Array.isArray(column.children) && column.children.length > 0;
}

const getHeaderDepth = (columns: TableColumn<T>[]): number => {
  let maxDepth = 1;
  for (const column of columns) {
    if (hasChildren(column)) {
      const childDepth = getHeaderDepth(column.children!) + 1;
      maxDepth = Math.max(maxDepth, childDepth);
    }
  }
  return maxDepth;
};

const getColSpan = (column: TableColumn<T>): number => {
  if (!hasChildren(column)) return 1;
  return column.children!.reduce((sum, child) => sum + getColSpan(child), 0);
};

interface HeaderCell {
  column: TableColumn<T>;
  colSpan: number;
  rowSpan: number;
}

const getHeaderRows = computed<HeaderCell[][]>(() => {
  const columns = visibleColumns.value || [];
  const maxDepth = getHeaderDepth(columns);
  const rows: HeaderCell[][] = [];

  for (let i = 0; i < maxDepth; i++) {
    rows.push([]);
  }

  const collectCells = (cols: TableColumn<T>[], depth: number) => {
    for (const column of cols) {
      const colSpan = getColSpan(column);
      const isLeaf = !hasChildren(column);
      const rowSpan = isLeaf ? maxDepth - depth : 1;

      rows[depth]!.push({ column, colSpan, rowSpan });

      if (hasChildren(column)) {
        collectCells(column.children!, depth + 1);
      }
    }
  };

  collectCells(columns, 0);
  return rows;
});

const getLeafColumns = (columns: TableColumn<T>[]): TableColumn<T>[] => {
  const leaves: TableColumn<T>[] = [];
  const collect = (cols: TableColumn<T>[]) => {
    for (const column of cols) {
      if (hasChildren(column)) {
        collect(column.children!);
      } else {
        leaves.push(column);
      }
    }
  };
  collect(columns);
  return leaves;
};

const leafColumns = computed(() => getLeafColumns(visibleColumns.value || []));

const isMultiLevelHeader = computed(() => getHeaderDepth(visibleColumns.value || []) > 1);

// ==================== 列宽下限（按最长内容） ====================
const minColumnWidths = ref<Record<string, number>>({});

const isTitleColumn = (column: TableColumn<T>): boolean => {
  return column.dataIndex === "title" || column.key === "title" || column.title === "标题";
};

const toPlainText = (value: unknown): string => {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map((v) => String(v ?? "")).join(" / ");
  if (typeof value === "object") return "";
  return String(value);
};

const measureTextWidth = (text: string): number => {
  if (!text) return 0;
  if (typeof document === "undefined") return text.length * 14;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return text.length * 14;
  ctx.font = "500 14px sans-serif";
  return ctx.measureText(text).width;
};

const recalcMinColumnWidths = () => {
  const result: Record<string, number> = {};
  const rows = tableData.value || [];
  const leaves = leafColumns.value || [];

  for (const column of leaves) {
    const key = getColumnKey(column);
    if (!key) continue;

    // 标题列允许自由缩窄，最小宽度只保留很小的兜底值
    if (isTitleColumn(column)) {
      result[key] = 60;
      continue;
    }

    const headerText = toPlainText(column.title);
    let maxW = measureTextWidth(headerText);

    let hasArray = false;
    let minChipTextLen = Infinity;

    for (const row of rows) {
      const cellValue = getCellValue(row, column);
      if (Array.isArray(cellValue)) {
        hasArray = true;
        for (const item of cellValue) {
          const len = String(item ?? "").length;
          if (len > 0 && len < minChipTextLen) minChipTextLen = len;
        }
        continue;
      }
      const cellText = toPlainText(cellValue);
      maxW = Math.max(maxW, measureTextWidth(cellText));
    }

    if (hasArray && minChipTextLen < Infinity) {
      const chipW = Math.max(36, minChipTextLen * 13 + 14);
      const arrayMinW = chipW + 4 + 34 + 14;
      maxW = Math.max(maxW, arrayMinW);
    }

    // 文本宽度 + 左右内边距 + 排序图标/安全余量
    const computedMin = Math.ceil(maxW + 40);
    result[key] = Math.max(80, computedMin);
  }

  minColumnWidths.value = result;
};

watch([leafColumns, tableData], recalcMinColumnWidths, { immediate: true, deep: true });

// ==================== 分页 ====================
const internalPagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
  showPagination: true
});

watch(
  () => props.pagination,
  (val) => {
    if (typeof val === "object") {
      if (val.current !== undefined) internalPagination.value.current = val.current;
      if (val.pageSize !== undefined) internalPagination.value.pageSize = val.pageSize;
      if (val.total !== undefined) internalPagination.value.total = val.total;
      if (val.showPagination !== undefined) internalPagination.value.showPagination = val.showPagination;

      if (val.current !== undefined) current.value = val.current;
      if (val.pageSize !== undefined) pageSize.value = val.pageSize;
    }
  },
  { immediate: true, deep: true }
);

// ==================== 排序处理 ====================
const handleSort = (column: TableColumn<T>) => {
  if (!column.sorter) return;

  const field = column.dataIndex || column.key || "";
  let newOrder: "ascend" | "descend" | null;

  if (sortState.value.field !== field) {
    newOrder = "ascend";
  } else if (sortState.value.order === "ascend") {
    newOrder = "descend";
  } else if (sortState.value.order === "descend") {
    newOrder = null;
  } else {
    newOrder = "ascend";
  }

  sortState.value = { field: newOrder ? field : "", order: newOrder };
  current.value = 1;

  emit("sortChange", { field, order: newOrder });
  fetchData();
};

const getColumnSortOrder = (column: TableColumn<T>): "ascend" | "descend" | null => {
  const field = column.dataIndex || column.key || "";
  if (sortState.value.field === field) {
    return sortState.value.order;
  }
  return null;
};

// ==================== 分页处理 ====================
const handlePageChange = (page: number) => {
  current.value = page;
  emit("paginationChange", { current: page, pageSize: pageSize.value });
  fetchData();
};

const handlePageSizeChange = (size: number) => {
  pageSize.value = size;
  current.value = 1;
  emit("paginationChange", { current: 1, pageSize: size });
  fetchData();
};

// ==================== 选择处理 ====================
const isAllSelected = computed(() => {
  if (!props.rowSelection || tableData.value.length === 0) return false;
  let hasEnabled = false;
  for (let i = 0; i < tableData.value.length; i++) {
    const record = tableData.value[i];
    if (record === undefined) continue;
    const checkboxProps = props.rowSelection?.getCheckboxProps?.(record);
    if (checkboxProps?.disabled) continue;
    hasEnabled = true;
    const key = getRowKey(record, i);
    if (!selectedRowKeys.value.includes(key)) return false;
  }
  return hasEnabled;
});

const isIndeterminate = computed(() => {
  if (!props.rowSelection || tableData.value.length === 0) return false;
  const enabledRecords = tableData.value.filter((record) => {
    const checkboxProps = props.rowSelection?.getCheckboxProps?.(record);
    return !checkboxProps?.disabled;
  });
  if (enabledRecords.length === 0) return false;
  const selectedCount = enabledRecords.filter((record, i) => {
    const key = getRowKey(record, i);
    return selectedRowKeys.value.includes(key);
  }).length;
  return selectedCount > 0 && selectedCount < enabledRecords.length;
});

const handleSelectAll = (checked: boolean) => {
  const enabledRecords = tableData.value.filter((record) => {
    const checkboxProps = props.rowSelection?.getCheckboxProps?.(record);
    return !checkboxProps?.disabled;
  });

  if (checked) {
    const newKeys = enabledRecords.map((record, i) => getRowKey(record, i));
    selectedRowKeys.value = [...new Set([...selectedRowKeys.value, ...newKeys])];
  } else {
    const currentPageKeys = enabledRecords.map((record, i) => getRowKey(record, i));
    selectedRowKeys.value = selectedRowKeys.value.filter((key) => !currentPageKeys.includes(key));
  }

  const selectedRows = tableData.value.filter((r, i) =>
    selectedRowKeys.value.includes(getRowKey(r, i))
  );
  emit("selectionChange", selectedRowKeys.value, selectedRows);
  props.rowSelection?.onChange?.(selectedRowKeys.value, selectedRows);
};

const handleSelect = (record: T, checked: boolean, index: number) => {
  const key = getRowKey(record, index);

  if (props.rowSelection?.type === "radio") {
    selectedRowKeys.value = checked ? [key] : [];
  } else {
    if (checked) {
      selectedRowKeys.value = [...selectedRowKeys.value, key];
    } else {
      selectedRowKeys.value = selectedRowKeys.value.filter((k) => k !== key);
    }
  }

  const selectedRows = tableData.value.filter((r, i) =>
    selectedRowKeys.value.includes(getRowKey(r, i))
  );
  emit("selectionChange", selectedRowKeys.value, selectedRows);
  props.rowSelection?.onChange?.(selectedRowKeys.value, selectedRows);
};

const isRowSelected = (record: T, index: number): boolean => {
  return selectedRowKeys.value.includes(getRowKey(record, index));
};

// ==================== 刷新 ====================
const handleRefresh = () => {
  emit("refresh");
  fetchData();
};

// ==================== 列顺序设置 ====================
const columnSettingOpen = ref(false);

const canManualOrder = computed(() => {
  const columns = baseVisibleColumns.value || [];
  return columns.length > 1 && columns.every((column) => !hasChildren(column));
});

const orderedColumnSettingItems = computed(() => {
  if (!canManualOrder.value) return [];
  return (visibleColumns.value || []).map((column) => ({
    key: getColumnKey(column),
    title: String(column.title || column.dataIndex || column.key || "未命名列")
  }));
});

const toggleColumnSetting = () => {
  columnSettingOpen.value = !columnSettingOpen.value;
};

const moveColumn = (columnKey: string, direction: -1 | 1) => {
  const nextOrder = [...columnOrderKeys.value];
  const currentIndex = nextOrder.indexOf(columnKey);
  if (currentIndex < 0) return;
  const targetIndex = currentIndex + direction;
  if (targetIndex < 0 || targetIndex >= nextOrder.length) return;
  const temp = nextOrder[targetIndex]!;
  nextOrder[targetIndex] = nextOrder[currentIndex]!;
  nextOrder[currentIndex] = temp;
  columnOrderKeys.value = nextOrder;
};

// ==================== 样式 ====================
const containerClass = computed(() => {
  const classes = ["vort-pro-table-container"];
  if (props.bordered) classes.push("vort-pro-table-bordered");
  classes.push(`vort-pro-table-${props.size}`);
  if (props.cellPadding === "none") classes.push("vort-pro-table-cell-padding-none");
  if (props.scroll?.y) classes.push("vort-pro-table-fixed-header");
  return classes;
});

const containerStyle = computed<Record<string, string>>(() => {
  const showLeftShadow = scrollState.value.hasScrollbar && !scrollState.value.isScrollLeft;
  const showRightShadow = scrollState.value.hasScrollbar && !scrollState.value.isScrollRight;

  return {
    "--vort-pro-table-left-shadow": showLeftShadow ? "inset 10px 0 8px -8px rgba(0, 0, 0, 0.1)" : "none",
    "--vort-pro-table-right-shadow": showRightShadow ? "inset -10px 0 8px -8px rgba(0, 0, 0, 0.1)" : "none",
  };
});

const scrollStyle = computed<Record<string, string>>(() => {
  const style: Record<string, string> = {
    overflowX: "auto",
  };

  const computedMaxHeight = props.scroll?.y
    ? typeof props.scroll.y === "number"
      ? `${props.scroll.y}px`
      : props.scroll.y
    : undefined;

  if (computedMaxHeight) {
    style.overflowY = "auto";
    style.maxHeight = computedMaxHeight;
  }

  return style;
});

const emptyFixedWidth = computed(() =>
  scrollContainerWidth.value > 0 ? `${scrollContainerWidth.value}px` : "100%",
);

// ==================== 列宽拖拽 ====================
const columnWidths = ref<Record<string, number>>({});

const getResolvedWidth = (column: TableColumn<T>): string | undefined => {
  const key = getColumnKey(column);
  const minW = minColumnWidths.value[key] || 50;
  const drag = columnWidths.value[key];
  if (drag) return `${Math.max(minW, drag)}px`;
  if (column.width) {
    if (typeof column.width === "number") return `${Math.max(minW, column.width)}px`;
    return column.width;
  }
  if (!isTitleColumn(column)) return `${minW}px`;
  return undefined;
};

const toPixelWidth = (column: TableColumn<T>): number => {
  const resolved = getResolvedWidth(column);
  if (resolved && resolved.endsWith("px")) {
    const parsed = Number.parseFloat(resolved);
    if (Number.isFinite(parsed)) return parsed;
  }
  return minColumnWidths.value[getColumnKey(column)] || 120;
};

const getColumnLeafList = (column: TableColumn<T>): TableColumn<T>[] => {
  return hasChildren(column) ? getLeafColumns([column]) : [column];
};

const getColumnFixedPlacement = (column: TableColumn<T>): "left" | "right" | undefined => {
  const placements = [...new Set(
    getColumnLeafList(column)
      .map((item) => item.fixed)
      .filter((placement): placement is "left" | "right" => placement === "left" || placement === "right")
  )];

  return placements.length === 1 ? placements[0] : undefined;
};

const hasFixedLeft = computed(() => leafColumns.value.some(c => c.fixed === "left"));
const hasFixedRight = computed(() => leafColumns.value.some(c => c.fixed === "right"));
const isSelectionFixed = computed(() => !!props.rowSelection && !!(props.rowSelection.fixed || hasFixedLeft.value));

const selectionColWidth = computed(() => {
  if (!props.rowSelection) return 0;
  const w = props.rowSelection.columnWidth;
  return typeof w === "number" ? w : parseInt(String(w || "48"), 10);
});

const fixedLeftOffsets = computed<Record<string, number>>(() => {
  const offsets: Record<string, number> = {};
  let currentLeft = isSelectionFixed.value ? selectionColWidth.value : 0;
  for (const column of leafColumns.value) {
    const key = getColumnKey(column);
    if (!key) continue;
    if (column.fixed === "left") {
      offsets[key] = currentLeft;
      currentLeft += toPixelWidth(column);
    }
  }
  return offsets;
});

const fixedRightOffsets = computed<Record<string, number>>(() => {
  const offsets: Record<string, number> = {};
  let currentRight = 0;

  for (const column of [...leafColumns.value].reverse()) {
    const key = getColumnKey(column);
    if (!key) continue;
    if (column.fixed === "right") {
      offsets[key] = currentRight;
      currentRight += toPixelWidth(column);
    }
  }

  return offsets;
});

const tableMinWidth = computed(() => {
  let total = 0;
  if (props.rowSelection) {
    const w = props.rowSelection.columnWidth;
    total += typeof w === "number" ? w : parseInt(String(w || "48"), 10);
  }
  for (const column of leafColumns.value) {
    total += toPixelWidth(column);
  }
  return total;
});

const tableStyle = computed<Record<string, string>>(() => {
  const style: Record<string, string> = {
    width: "100%",
    minWidth: `${tableMinWidth.value}px`,
    tableLayout: "fixed",
  };

  if (props.scroll?.x) {
    style.width = typeof props.scroll.x === "number" ? `${props.scroll.x}px` : props.scroll.x;
  }

  return style;
});

const getFixedCellStyle = (column: TableColumn<T>, isHeader = false): Record<string, string> => {
  const fixedPlacement = getColumnFixedPlacement(column);
  if (!fixedPlacement) return {};

  const leafColumnsForCell = getColumnLeafList(column);
  const style: Record<string, string> = {
    position: "sticky",
    zIndex: isHeader ? "8" : "4",
  };

  if (isHeader) {
    style.background = "var(--vort-table-header-bg, #fafafa)";
  }

  if (fixedPlacement === "left") {
    const firstLeaf = leafColumnsForCell[0];
    const key = firstLeaf ? getColumnKey(firstLeaf) : "";
    style.left = `${fixedLeftOffsets.value[key] || 0}px`;
  }

  if (fixedPlacement === "right") {
    const lastLeaf = leafColumnsForCell[leafColumnsForCell.length - 1];
    const key = lastLeaf ? getColumnKey(lastLeaf) : "";
    style.right = `${fixedRightOffsets.value[key] || 0}px`;
  }

  return style;
};

const getSelectionCellStyle = (isHeader = false): Record<string, string> => {
  if (!isSelectionFixed.value) return {};

  const style: Record<string, string> = {
    position: "sticky",
    left: "0px",
    zIndex: isHeader ? "9" : "5",
  };

  if (isHeader) {
    style.background = "var(--vort-table-header-bg, #fafafa)";
  }

  return style;
};

const lastFixedLeftKey = computed<string>(() => {
  let last = "";
  for (const column of leafColumns.value) {
    if (column.fixed === "left") {
      last = getColumnKey(column);
    }
  }
  return last;
});

const firstFixedRightKey = computed<string>(() => {
  for (const column of leafColumns.value) {
    if (column.fixed === "right") {
      return getColumnKey(column);
    }
  }
  return "";
});

const isFixedBoundaryColumn = (column: TableColumn<T>): boolean => {
  const fixedPlacement = getColumnFixedPlacement(column);
  if (!fixedPlacement) return false;

  const leafKeys = getColumnLeafList(column)
    .map((item) => getColumnKey(item))
    .filter(Boolean);

  if (leafKeys.length === 0) return false;

  if (fixedPlacement === "left") {
    return leafKeys[leafKeys.length - 1] === lastFixedLeftKey.value;
  }

  return leafKeys[0] === firstFixedRightKey.value;
};

const isSelectionColumnFixedBoundary = computed(() => isSelectionFixed.value && !hasFixedLeft.value);

const getFixedClassName = (column: TableColumn<T>): Array<string | false> => {
  const fixedPlacement = getColumnFixedPlacement(column);
  return [
    !!fixedPlacement && "vort-pro-table-cell-fixed",
    fixedPlacement === "left" && "vort-pro-table-cell-fixed-left",
    fixedPlacement === "right" && "vort-pro-table-cell-fixed-right",
    isFixedBoundaryColumn(column) && "vort-pro-table-cell-fixed-boundary",
  ];
};

const getSelectionColumnClass = (): Array<string | false> => [
  "vort-pro-table-selection-column",
  isSelectionFixed.value && "vort-pro-table-cell-fixed",
  isSelectionFixed.value && "vort-pro-table-cell-fixed-left",
  isSelectionColumnFixedBoundary.value && "vort-pro-table-cell-fixed-boundary",
];

const tableWrapperRef = ref<HTMLElement | null>(null);
const scrollState = ref({
  isScrollLeft: true,
  isScrollRight: true,
  hasScrollbar: false,
});
const scrollContainerWidth = ref(0);
let contentResizeObserver: ResizeObserver | null = null;

const updateScrollState = () => {
  const wrapper = tableWrapperRef.value;
  if (!wrapper) {
    scrollState.value = {
      isScrollLeft: true,
      isScrollRight: true,
      hasScrollbar: false,
    };
    scrollContainerWidth.value = 0;
    return;
  }

  const maxScrollLeft = Math.max(wrapper.scrollWidth - wrapper.clientWidth, 0);
  scrollState.value = {
    isScrollLeft: wrapper.scrollLeft <= 0,
    isScrollRight: wrapper.scrollLeft >= maxScrollLeft - 1,
    hasScrollbar: maxScrollLeft > 1,
  };
  scrollContainerWidth.value = wrapper.clientWidth;
};

const handleTableWrapperScroll = () => {
  updateScrollState();
};

onMounted(() => {
  nextTick(() => {
    updateScrollState();

    const el = tableWrapperRef.value;
    if (el) {
      contentResizeObserver = new ResizeObserver(() => {
        updateScrollState();
      });
      contentResizeObserver.observe(el);
      const table = el.querySelector(".vort-pro-table");
      if (table) contentResizeObserver.observe(table);
    }
  });
});

watch([leafColumns, tableData, columnWidths, () => props.scroll, () => props.rowSelection, hasFixedRight], () => {
  nextTick(() => {
    updateScrollState();
  });
}, { deep: true });

let resizingCol: string | null = null;
let resizeStartX = 0;
let resizeStartW = 0;
let resizingMinW = 50;
const isResizing = ref(false);

const onResizeStart = (e: MouseEvent, column: TableColumn<T>) => {
  e.preventDefault();
  e.stopPropagation();
  const key = getColumnKey(column);
  resizingCol = key;
  isResizing.value = true;
  resizeStartX = e.clientX;
  resizingMinW = isTitleColumn(column) ? 40 : (minColumnWidths.value[key] || 80);

  const existing = columnWidths.value[key];
  if (existing) {
    resizeStartW = existing;
  } else {
    const th = (e.target as HTMLElement).closest("th");
    resizeStartW = th ? th.offsetWidth : 120;
  }

  document.addEventListener("mousemove", onResizeMove);
  document.addEventListener("mouseup", onResizeEnd);
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
};

const onResizeMove = (e: MouseEvent) => {
  if (!resizingCol) return;
  const diff = e.clientX - resizeStartX;
  const newW = Math.max(resizingMinW, resizeStartW + diff);
  columnWidths.value = { ...columnWidths.value, [resizingCol]: newW };
};

const onResizeEnd = () => {
  resizingCol = null;
  isResizing.value = false;
  document.removeEventListener("mousemove", onResizeMove);
  document.removeEventListener("mouseup", onResizeEnd);
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  emit("columnWidthChange", { ...columnWidths.value });
};

onBeforeUnmount(() => {
  document.removeEventListener("mousemove", onResizeMove);
  document.removeEventListener("mouseup", onResizeEnd);
  contentResizeObserver?.disconnect();
  contentResizeObserver = null;
});

// ==================== 暴露方法 ====================
defineExpose({
  refresh: handleRefresh,
  clearSelection: () => { selectedRowKeys.value = []; },
  dataSource: internalDataSource,
  total,
  current,
  pageSize,
  columnWidths
});
</script>

<template>
  <div :class="containerClass" :style="containerStyle">
    <!-- 工具栏 -->
    <div v-if="toolbar !== false" class="vort-pro-table-toolbar">
      <div class="vort-pro-table-toolbar-left">
        <slot name="toolbar-left" />
      </div>
      <div class="vort-pro-table-toolbar-right">
        <slot name="toolbar-right" />
        <div v-if="toolbar?.columnSetting !== false" class="vort-pro-table-column-setting">
          <Popover v-model:open="columnSettingOpen" trigger="click" placement="bottomRight" :arrow="false">
            <VortTooltip title="列设置">
              <VortButton size="small" @click.stop="toggleColumnSetting">列设置</VortButton>
            </VortTooltip>
            <template #content>
              <div class="vort-pro-table-column-setting-panel">
                <div class="vort-pro-table-column-setting-title">手动移动列</div>
                <div v-if="canManualOrder" class="vort-pro-table-column-setting-list">
                  <div
                    v-for="(item, index) in orderedColumnSettingItems"
                    :key="item.key"
                    class="vort-pro-table-column-setting-item"
                  >
                    <span class="vort-pro-table-column-setting-name" :title="item.title">{{ item.title }}</span>
                    <div class="vort-pro-table-column-setting-actions">
                      <VortButton size="small" :disabled="index === 0" @click.stop="moveColumn(item.key, -1)">
                        上移
                      </VortButton>
                      <VortButton
                        size="small"
                        :disabled="index === orderedColumnSettingItems.length - 1"
                        @click.stop="moveColumn(item.key, 1)"
                      >
                        下移
                      </VortButton>
                    </div>
                  </div>
                </div>
                <div v-else class="vort-pro-table-column-setting-tip">当前表头结构不支持手动排序</div>
              </div>
            </template>
          </Popover>
        </div>
        <VortTooltip v-if="toolbar?.refresh !== false" title="刷新">
          <VortButton size="small" @click="handleRefresh">刷新</VortButton>
        </VortTooltip>
      </div>
    </div>

    <div class="vort-pro-table-content">
      <!-- 加载遮罩（覆盖整个表格区域：表头+表体+分页） -->
      <div v-if="(internalLoading || loading) && !isResizing" class="vort-pro-table-loading-mask">
        <Spin :spinning="true" />
      </div>

      <!-- 表格主体 -->
      <div class="vort-pro-table-wrapper">
        <div ref="tableWrapperRef" class="vort-pro-table-scroll" :style="scrollStyle" @scroll="handleTableWrapperScroll">
        <table class="vort-pro-table" :style="tableStyle">
        <colgroup>
          <col v-if="rowSelection" :style="{ width: rowSelection.columnWidth || '48px' }" />
          <col
            v-for="column in leafColumns"
            :key="column.key || column.dataIndex || column.title"
            :style="{ width: getResolvedWidth(column) }"
          />
        </colgroup>

        <!-- 表头 -->
        <thead class="vort-pro-table-thead">
          <!-- 多级表头 -->
          <template v-if="isMultiLevelHeader">
            <tr v-for="(headerRow, rowIndex) in getHeaderRows" :key="rowIndex">
              <th
                v-if="rowSelection && rowIndex === 0"
                :class="getSelectionColumnClass()"
                :rowspan="getHeaderRows.length"
                :style="{ width: rowSelection.columnWidth || '48px', ...getSelectionCellStyle(true) }"
              >
                <Checkbox
                  v-if="rowSelection.type !== 'radio'"
                  :checked="isAllSelected"
                  :indeterminate="isIndeterminate"
                  @update:checked="handleSelectAll"
                />
              </th>
              <th
                v-for="cell in headerRow"
                :key="cell.column.key || cell.column.dataIndex || cell.column.title"
                :class="[
                  'vort-pro-table-cell',
                  `vort-pro-table-align-${cell.column.align || 'center'}`,
                  cell.column.sorter && !hasChildren(cell.column) && 'vort-pro-table-cell-sortable',
                  getFixedClassName(cell.column),
                  cell.column.headerClassName
                ]"
                :colspan="cell.colSpan > 1 ? cell.colSpan : undefined"
                :rowspan="cell.rowSpan > 1 ? cell.rowSpan : undefined"
                :style="{ width: getResolvedWidth(cell.column), ...getFixedCellStyle(cell.column, true) }"
                @click="cell.column.sorter && !hasChildren(cell.column) ? handleSort(cell.column) : undefined"
              >
                <div class="vort-pro-table-column-header">
                  <slot :name="`header-${cell.column.slot || cell.column.dataIndex}`" :column="cell.column">
                    {{ cell.column.title }}
                  </slot>
                  <span v-if="cell.column.sorter && !hasChildren(cell.column)" class="vort-pro-table-column-sorter">
                    <CaretUpFilled
                      class="vort-pro-table-sorter-icon"
                      :class="{ active: getColumnSortOrder(cell.column) === 'ascend' }"
                    />
                    <CaretDownFilled
                      class="vort-pro-table-sorter-icon"
                      :class="{ active: getColumnSortOrder(cell.column) === 'descend' }"
                    />
                  </span>
                </div>
                    <span
                      v-if="!hasChildren(cell.column)"
                      class="vort-pro-table-resize-handle"
                      @mousedown="onResizeStart($event, cell.column)"
                      @click.stop
                    />
              </th>
            </tr>
          </template>
          <!-- 单级表头 -->
          <tr v-else>
            <th v-if="rowSelection" :class="getSelectionColumnClass()" :style="{ width: rowSelection.columnWidth || '48px', ...getSelectionCellStyle(true) }">
              <Checkbox
                v-if="rowSelection.type !== 'radio'"
                :checked="isAllSelected"
                :indeterminate="isIndeterminate"
                @update:checked="handleSelectAll"
              />
            </th>
            <th
              v-for="column in visibleColumns"
              :key="column.key || column.dataIndex || column.title"
              :class="[
                'vort-pro-table-cell',
                `vort-pro-table-align-${column.align || 'left'}`,
                column.sorter && 'vort-pro-table-cell-sortable',
                column.headerClassName,
                getFixedClassName(column)
              ]"
              :style="{ width: getResolvedWidth(column), ...getFixedCellStyle(column, true) }"
              @click="column.sorter ? handleSort(column) : undefined"
            >
              <div class="vort-pro-table-column-header">
                <slot :name="`header-${column.slot || column.dataIndex}`" :column="column">
                  {{ column.title }}
                </slot>
                <span v-if="column.sorter" class="vort-pro-table-column-sorter">
                  <CaretUpFilled class="vort-pro-table-sorter-icon" :class="{ active: getColumnSortOrder(column) === 'ascend' }" />
                  <CaretDownFilled class="vort-pro-table-sorter-icon" :class="{ active: getColumnSortOrder(column) === 'descend' }" />
                </span>
              </div>
              <span class="vort-pro-table-resize-handle" @mousedown="onResizeStart($event, column)" @click.stop />
            </th>
          </tr>
        </thead>

        <!-- 表体 -->
        <tbody class="vort-pro-table-tbody">
          <tr v-if="tableData.length === 0 && !internalLoading" class="vort-pro-table-empty-row">
            <td :colspan="(rowSelection ? 1 : 0) + leafColumns.length" class="vort-pro-table-empty-cell">
              <div class="vort-pro-table-empty-fixed" :style="{ width: emptyFixedWidth }">
                <slot name="empty">
                  <div class="vort-pro-table-empty">
                    <EmptyOutlined class="vort-pro-table-empty-icon" />
                    <span class="vort-pro-table-empty-text">暂无数据</span>
                  </div>
                </slot>
              </div>
            </td>
          </tr>

          <tr
            v-for="(record, index) in tableData"
            :key="getRowKey(record, index)"
            :class="['vort-pro-table-row', isRowSelected(record, index) && 'vort-pro-table-row-selected']"
          >
            <td v-if="rowSelection" :class="getSelectionColumnClass()" :style="getSelectionCellStyle()">
              <Checkbox
                :checked="isRowSelected(record, index)"
                :disabled="rowSelection.getCheckboxProps?.(record)?.disabled"
                @update:checked="(checked: boolean) => handleSelect(record, checked, index)"
              />
            </td>
            <td
              v-for="column in leafColumns"
              :key="column.key || column.dataIndex || column.title"
              :class="[
                'vort-pro-table-cell',
                `vort-pro-table-align-${column.align || 'left'}`,
                column.ellipsis && 'vort-pro-table-cell-ellipsis',
                column.className,
                getFixedClassName(column)
              ]"
              :style="getFixedCellStyle(column)"
            >
              <slot
                :name="column.slot || column.dataIndex"
                :text="getCellValue(record, column)"
                :record="record"
                :index="index"
                :column="column"
                :resolved-width="getResolvedWidth(column)"
              >
                {{ getCellValue(record, column) }}
              </slot>
            </td>
          </tr>
        </tbody>
        </table>
        </div>
      </div>

      <!-- 分页 -->
      <div
        v-if="pagination !== false && internalPagination.showPagination && total > 0"
        class="vort-pro-table-pagination"
      >
        <Pagination
          :current="current"
          :page-size="pageSize"
          :total="total"
          :show-size-changer="pagination?.showSizeChanger ?? false"
          :show-quick-jumper="pagination?.showQuickJumper ?? false"
          :page-size-options="pagination?.pageSizeOptions ?? [10, 20, 50, 100]"
          @update:current="handlePageChange"
          @update:page-size="handlePageSizeChange"
        />
      </div>
    </div>
  </div>
</template>

<style lang="less" scoped>
.vort-pro-table-container {
  position: relative;
  width: 100%;
  font-size: 14px;
  color: var(--vort-text, #333);
  background: var(--vort-bg-elevated, #fff);
}

.vort-pro-table-content {
  position: relative;
}

.vort-pro-table-loading-mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.6);
}

.vort-pro-table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
}

.vort-pro-table-toolbar-left,
.vort-pro-table-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vort-pro-table-column-setting {
  position: relative;
}

.vort-pro-table-column-setting-panel {
  width: 280px;
  max-height: 320px;
  overflow: auto;
  padding: 4px;
}

.vort-pro-table-column-setting-title {
  font-size: 13px;
  color: #475569;
  margin-bottom: 8px;
}

.vort-pro-table-column-setting-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vort-pro-table-column-setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid #eef2f7;
  border-radius: 6px;
  padding: 6px 8px;
}

.vort-pro-table-column-setting-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #334155;
}

.vort-pro-table-column-setting-actions {
  display: inline-flex;
  gap: 4px;
}

.vort-pro-table-column-setting-tip {
  font-size: 12px;
  color: #94a3b8;
}

.vort-pro-table-wrapper {
  position: relative;
  z-index: 1;
  overflow: hidden;
}

.vort-pro-table-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  max-width: 100%;
}

.vort-pro-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
}

.vort-pro-table-fixed-header .vort-pro-table-thead {
  position: relative;
  z-index: 4;
}

.vort-pro-table-fixed-header .vort-pro-table-thead th {
  position: sticky;
  top: 0;
  z-index: 5;
  background: var(--vort-table-header-bg, #fafafa);
}

.vort-pro-table-fixed-header .vort-pro-table-tbody {
  position: relative;
  z-index: 1;
}

.vort-pro-table-thead th {
  position: relative;
  background: var(--vort-table-header-bg, #fafafa);
  padding: 16px;
  font-weight: 600;
  text-align: left;
  vertical-align: middle;
  border-bottom: 1px solid #eceff3;
  border-right: 1px solid #f3f5f8;
  white-space: nowrap;
}

.vort-pro-table-thead th:last-child {
  border-right: none;
}

.vort-pro-table-resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 8px;
  cursor: col-resize;
  z-index: 2;

  &::after {
    content: "";
    position: absolute;
    top: 25%;
    bottom: 25%;
    right: 0;
    width: 1px;
    background: transparent;
    transition: background 0.15s;
  }

  &:hover::after {
    background: var(--vort-primary);
  }
}

.vort-pro-table-cell-sortable {
  cursor: pointer;
  user-select: none;
}

.vort-pro-table-column-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.vort-pro-table-column-sorter {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  margin-left: 4px;
  line-height: 0;
}

.vort-pro-table-sorter-icon {
  width: 10px;
  height: 10px;
  color: #bfbfbf;

  &:first-child {
    margin-bottom: -1px;
  }

  &:last-child {
    margin-top: -2px;
  }

  &.active {
    color: var(--vort-primary);
  }
}

.vort-pro-table-tbody tr {
  transition: background-color 0.2s;
}

.vort-pro-table-tbody tr:hover {
  background: #fafafa;
}

.vort-pro-table-tbody td {
  padding: 16px;
  vertical-align: middle;
  border-bottom: 1px solid #eceff3;
  border-right: 1px solid #f3f5f8;
  white-space: nowrap;
}

.vort-pro-table-tbody td:last-child {
  border-right: none;
}

.vort-pro-table-thead th.vort-pro-table-selection-column,
.vort-pro-table-tbody td.vort-pro-table-selection-column {
  width: 48px;
  padding: 16px 12px;
  text-align: center;
}

.vort-pro-table-align-left {
  text-align: left;
}

.vort-pro-table-align-center {
  text-align: center;
}

.vort-pro-table-align-right {
  text-align: right;
}

.vort-pro-table-cell-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.6;
}

.vort-pro-table-cell-fixed {
  position: sticky;
  z-index: 4;
  background: var(--vort-bg-elevated, #fff);
  background-clip: padding-box;
  overflow: visible;
  transition: background-color 0.2s;
}

.vort-pro-table-thead .vort-pro-table-cell-fixed {
  z-index: 8;
  background: var(--vort-table-header-bg, #fafafa);
}

.vort-pro-table-cell-fixed-left.vort-pro-table-cell-fixed-boundary::after,
.vort-pro-table-cell-fixed-right.vort-pro-table-cell-fixed-boundary::before {
  content: "";
  position: absolute;
  top: 0;
  bottom: 0;
  width: 20px;
  z-index: 2;
  pointer-events: none;
  transition: box-shadow 0.2s;
}

.vort-pro-table-cell-fixed-left.vort-pro-table-cell-fixed-boundary::after {
  right: -20px;
  box-shadow: var(--vort-pro-table-left-shadow, none);
}

.vort-pro-table-cell-fixed-right.vort-pro-table-cell-fixed-boundary::before {
  left: -20px;
  box-shadow: var(--vort-pro-table-right-shadow, none);
}

.vort-pro-table-thead .vort-pro-table-cell-fixed-left.vort-pro-table-cell-fixed-boundary::after,
.vort-pro-table-thead .vort-pro-table-cell-fixed-right.vort-pro-table-cell-fixed-boundary::before {
  z-index: 1;
}

.vort-pro-table-tbody tr:hover .vort-pro-table-cell-fixed {
  background: #fafafa;
}

.vort-pro-table-row-selected {
  background: #e6f4ff;
}

.vort-pro-table-row-selected .vort-pro-table-cell-fixed {
  background: #e6f4ff;
}

.vort-pro-table-row-selected:hover {
  background: #bae0ff;
}

.vort-pro-table-row-selected:hover .vort-pro-table-cell-fixed {
  background: #bae0ff;
}

.vort-pro-table-empty-row:hover {
  background: transparent;
}

.vort-pro-table-empty-cell {
  padding: 0;
}

.vort-pro-table-empty-fixed {
  position: sticky;
  left: 0;
  overflow: hidden;
  padding: 80px 16px;
}

.vort-pro-table-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #bfbfbf;
  margin:60px 0
}

.vort-pro-table-empty-icon {
  width: 140px;
  height: 100px;
}

.vort-pro-table-empty-text {
  font-size: 14px;
  color: #b0b0b0;
  letter-spacing: 0.5px;
}

.vort-pro-table-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0;
}

/* 尺寸变体 */
.vort-pro-table-large .vort-pro-table-thead th,
.vort-pro-table-large .vort-pro-table-tbody td {
  padding: 20px 16px;
}

.vort-pro-table-middle .vort-pro-table-thead th,
.vort-pro-table-middle .vort-pro-table-tbody td {
  padding: 8px;
}

.vort-pro-table-middle .vort-pro-table-thead th.vort-pro-table-selection-column,
.vort-pro-table-middle .vort-pro-table-tbody td.vort-pro-table-selection-column {
  padding: 8px 6px;
}

.vort-pro-table-small .vort-pro-table-thead th,
.vort-pro-table-small .vort-pro-table-tbody td {
  padding: 8px 12px;
}

.vort-pro-table-small {
  font-size: 13px;
}

/* 无内边距模式：只清除 td，th 保留 padding 以显示表头文字 */
.vort-pro-table-cell-padding-none .vort-pro-table-tbody td {
  padding: 0 !important;
  min-height: 32px;
}

.vort-pro-table-cell-padding-none .vort-pro-table-tbody .vort-pro-table-selection-column {
  padding: 0 !important;
  min-height: 32px;
}

/* 边框 */
.vort-pro-table-bordered .vort-pro-table-wrapper {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
}
</style>

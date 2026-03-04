<script setup lang="ts" generic="T = any">
import { ref, computed, watch } from "vue";
import { Checkbox, Spin, Pagination } from "@/components/vort";
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
  request?: (params: ProTableRequestParams) => Promise<ProTableResponse<T>>;
  params?: Record<string, any>;
  rowKey?: string | ((record: T) => string | number);
  bordered?: boolean;
  size?: TableSize;
  loading?: boolean;
  pagination?: TablePagination | false;
  rowSelection?: TableRowSelection<T>;
  scroll?: TableScroll;
  toolbar?: any;
}

const props = withDefaults(defineProps<Props<T>>(), {
  columns: () => [],
  dataSource: () => [],
  params: () => ({}),
  rowKey: "id",
  bordered: false,
  size: "middle",
  loading: false,
  pagination: () => ({ current: 1, pageSize: 10, total: 0, showPagination: true }),
  toolbar: () => ({ refresh: true, columnSetting: true })
});

const emit = defineEmits<{
  requestChange: [params: ProTableRequestParams];
  paginationChange: [pagination: { current: number; pageSize: number }];
  sortChange: [sorter: { field: string; order: "ascend" | "descend" | null }];
  filterChange: [filters: Record<string, any>];
  selectionChange: [selectedRowKeys: (string | number)[], selectedRows: T[]];
  refresh: [];
}>();

// ==================== 数据状态 ====================
const internalDataSource = ref<T[]>([]);
const total = ref(0);
const current = ref(1);
const pageSize = ref(10);
const internalLoading = ref(false);

const requestParams = ref<ProTableRequestParams>({
  current: 1,
  pageSize: 10,
  ...props.params
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

// ==================== 多级表头支持 ====================
const hasChildren = (column: TableColumn<T>): boolean => {
  return Array.isArray(column.children) && column.children.length > 0;
};

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
  const columns = props.columns || [];
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

const leafColumns = computed(() => getLeafColumns(props.columns || []));

const isMultiLevelHeader = computed(() => getHeaderDepth(props.columns || []) > 1);

// ==================== 分页 ====================
const internalPagination = ref({
  current: 1,
  pageSize: 10,
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
  if (!props.rowSelection || internalDataSource.value.length === 0) return false;
  let hasEnabled = false;
  for (let i = 0; i < internalDataSource.value.length; i++) {
    const record = internalDataSource.value[i];
    const checkboxProps = props.rowSelection?.getCheckboxProps?.(record);
    if (checkboxProps?.disabled) continue;
    hasEnabled = true;
    const key = getRowKey(record, i);
    if (!selectedRowKeys.value.includes(key)) return false;
  }
  return hasEnabled;
});

const isIndeterminate = computed(() => {
  if (!props.rowSelection || internalDataSource.value.length === 0) return false;
  const enabledRecords = internalDataSource.value.filter((record) => {
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
  const enabledRecords = internalDataSource.value.filter((record) => {
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

  const selectedRows = (props.dataSource || internalDataSource.value).filter((r, i) =>
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

  const selectedRows = (props.dataSource || internalDataSource.value).filter((r, i) =>
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

// ==================== 样式 ====================
const containerClass = computed(() => {
  const classes = ["vort-pro-table-container"];
  if (props.bordered) classes.push("vort-pro-table-bordered");
  classes.push(`vort-pro-table-${props.size}`);
  return classes;
});

// ==================== 暴露方法 ====================
defineExpose({
  refresh: handleRefresh,
  dataSource: internalDataSource,
  total,
  current,
  pageSize
});
</script>

<template>
  <div :class="containerClass">
    <!-- 工具栏 -->
    <div v-if="toolbar !== false" class="vort-pro-table-toolbar">
      <div class="vort-pro-table-toolbar-left">
        <slot name="toolbar-left" />
      </div>
      <div class="vort-pro-table-toolbar-right">
        <slot name="toolbar-right" />
        <button v-if="toolbar?.refresh !== false" class="vort-pro-table-toolbar-btn" title="刷新" @click="handleRefresh">
          刷新
        </button>
      </div>
    </div>

    <!-- 加载遮罩 -->
    <Spin :spinning="internalLoading || loading" class="vort-pro-table-spin" />

    <!-- 表格主体 -->
    <div class="vort-pro-table-wrapper">
      <table class="vort-pro-table">
        <colgroup>
          <col v-if="rowSelection" :style="{ width: rowSelection.columnWidth || '48px' }" />
          <col
            v-for="column in leafColumns"
            :key="column.key || column.dataIndex || column.title"
            :style="{ width: column.width ? (typeof column.width === 'number' ? `${column.width}px` : column.width) : undefined }"
          />
        </colgroup>

        <!-- 表头 -->
        <thead class="vort-pro-table-thead">
          <!-- 多级表头 -->
          <template v-if="isMultiLevelHeader">
            <tr v-for="(headerRow, rowIndex) in getHeaderRows" :key="rowIndex">
              <th
                v-if="rowSelection && rowIndex === 0"
                class="vort-pro-table-selection-column"
                :rowspan="getHeaderRows.length"
                :style="{ width: rowSelection.columnWidth || '48px' }"
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
                  cell.column.headerClassName
                ]"
                :colspan="cell.colSpan > 1 ? cell.colSpan : undefined"
                :rowspan="cell.rowSpan > 1 ? cell.rowSpan : undefined"
                :style="{ width: cell.column.width }"
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
              </th>
            </tr>
          </template>
          <!-- 单级表头 -->
          <tr v-else>
            <th v-if="rowSelection" class="vort-pro-table-selection-column" :style="{ width: rowSelection.columnWidth || '48px' }">
              <Checkbox
                v-if="rowSelection.type !== 'radio'"
                :checked="isAllSelected"
                :indeterminate="isIndeterminate"
                @update:checked="handleSelectAll"
              />
            </th>
            <th
              v-for="column in (columns || [])"
              :key="column.key || column.dataIndex || column.title"
              :class="[
                'vort-pro-table-cell',
                `vort-pro-table-align-${column.align || 'left'}`,
                column.sorter && 'vort-pro-table-cell-sortable',
                column.headerClassName
              ]"
              :style="{ width: column.width }"
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
            </th>
          </tr>
        </thead>

        <!-- 表体 -->
        <tbody class="vort-pro-table-tbody">
          <tr v-if="(dataSource || internalDataSource).length === 0 && !internalLoading" class="vort-pro-table-empty-row">
            <td :colspan="(rowSelection ? 1 : 0) + leafColumns.length" class="vort-pro-table-empty-cell">
              <slot name="empty">
                <div class="vort-pro-table-empty">
                  <EmptyOutlined class="vort-pro-table-empty-icon" />
                  <span class="vort-pro-table-empty-text">暂无数据</span>
                </div>
              </slot>
            </td>
          </tr>

          <tr
            v-for="(record, index) in (dataSource || internalDataSource)"
            :key="getRowKey(record, index)"
            :class="['vort-pro-table-row', isRowSelected(record, index) && 'vort-pro-table-row-selected']"
          >
            <td v-if="rowSelection" class="vort-pro-table-selection-column">
              <Checkbox
                :checked="isRowSelected(record, index)"
                :disabled="rowSelection.getCheckboxProps?.(record)?.disabled"
                @update:checked="(checked: boolean) => handleSelect(record, checked, index)"
              />
            </td>
            <td
              v-for="column in leafColumns"
              :key="column.key || column.dataIndex || column.title"
              :class="['vort-pro-table-cell', `vort-pro-table-align-${column.align || 'left'}`, column.ellipsis && 'vort-pro-table-cell-ellipsis', column.className]"
            >
              <slot
                :name="column.slot || column.dataIndex"
                :text="getCellValue(record, column)"
                :record="record"
                :index="index"
                :column="column"
              >
                {{ getCellValue(record, column) }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
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
</template>

<style lang="less" scoped>
.vort-pro-table-container {
  position: relative;
  width: 100%;
  font-size: 14px;
  color: var(--vort-text, #333);
  background: var(--vort-bg-elevated, #fff);
}

.vort-pro-table-spin {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 10;
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

.vort-pro-table-toolbar-btn {
  padding: 4px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;

  &:hover {
    color: #4096ff;
    border-color: #4096ff;
  }
}

.vort-pro-table-wrapper {
  overflow-x: auto;
}

.vort-pro-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: auto;
}

.vort-pro-table-thead {
  background: var(--vort-table-header-bg, #fafafa);
}

.vort-pro-table-thead th {
  padding: 16px;
  font-weight: 600;
  text-align: left;
  border-bottom: 1px solid var(--vort-border-secondary, #f0f0f0);
  white-space: nowrap;
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
  margin-left: 4px;
}

.vort-pro-table-sorter-icon {
  width: 10px;
  height: 10px;
  color: #bfbfbf;

  &.active {
    color: #4096ff;
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
  border-bottom: 1px solid var(--vort-border-secondary, #f0f0f0);
}

.vort-pro-table-selection-column {
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
  max-width: 200px;
}

.vort-pro-table-row-selected {
  background: #e6f4ff;
}

.vort-pro-table-row-selected:hover {
  background: #bae0ff;
}

.vort-pro-table-empty-row:hover {
  background: transparent;
}

.vort-pro-table-empty-cell {
  padding: 48px 16px;
  text-align: center;
}

.vort-pro-table-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #8c8c8c;
}

.vort-pro-table-empty-icon {
  width: 64px;
  height: 64px;
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
  padding: 16px;
}

.vort-pro-table-small .vort-pro-table-thead th,
.vort-pro-table-small .vort-pro-table-tbody td {
  padding: 8px 12px;
}

.vort-pro-table-small {
  font-size: 13px;
}

/* 边框 */
.vort-pro-table-bordered .vort-pro-table-wrapper {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
}
</style>

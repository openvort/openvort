<script setup lang="ts">
import { computed, ref, watch, provide, useSlots, nextTick, onUnmounted, onMounted, reactive } from "vue";
import { Checkbox, Spin, Pagination } from "@/components/vort";
import { CaretUpFilled, CaretDownFilled, EmptyOutlined, LoadingOutlined } from "@/components/vort/icons";
import { useVirtualScroll } from "@/components/vort/composables";
import { useLocale } from "../locale";
import { CellRenderer, HeaderRenderer } from "./renderers";
import type {
    TableColumn,
    TablePagination,
    TableRowSelection,
    TableScroll,
    TableSize,
    SortState,
    TableContext,
    TableTreeProps,
    TreeNodeState,
    LoadChildrenFn
} from "./types";
import { TABLE_INJECTION_KEY } from "./types";

defineOptions({ name: "VortTable" });

const slots = useSlots();

// 国际化
const { t } = useLocale("Table");

/** Vort Table - 表格组件 */

interface Props<T = any> {
    /** 列配置（与 TableColumn 子组件二选一） */
    columns?: TableColumn<T>[];
    /** 数据源 */
    dataSource?: T[];
    /** 行 key 的取值字段或函数 */
    rowKey?: string | ((record: T) => string | number);
    /** 是否显示边框 */
    bordered?: boolean;
    /** 表格尺寸 */
    size?: TableSize;
    /** 是否加载中 */
    loading?: boolean;
    /** 分页配置，设为 false 关闭分页 */
    pagination?: TablePagination | false;
    /** 行选择配置 */
    rowSelection?: TableRowSelection<T>;
    /** 滚动配置 */
    scroll?: TableScroll;
    /** 表格包装器最小高度（用于覆盖全局样式，如主题中 min-height: 300px） */
    minHeight?: number | string;
    /** 表格包装器最大高度（不传时默认使用 scroll.y 作为 max-height） */
    maxHeight?: number | string;
    /** 空状态文案 */
    emptyText?: string;
    /** 是否显示表头 */
    showHeader?: boolean;
    /** 是否斑马纹 */
    stripe?: boolean;
    /** 行类名 */
    rowClassName?: string | ((record: T, index: number) => string);
    /** 自定义类名 */
    class?: string;
    // ==================== 树形表格配置 ====================
    /** 树形结构配置 */
    treeProps?: TableTreeProps;
    /** 懒加载子节点方法 */
    loadChildren?: LoadChildrenFn<T>;
    /** 默认展开的行 keys */
    defaultExpandedRowKeys?: (string | number)[];
    /** 受控的展开行 keys */
    expandedRowKeys?: (string | number)[];
    /** 是否点击行展开 */
    expandRowByClick?: boolean;
    /** 树形缩进，默认 30px */
    indent?: number;
    /** 懒加载时是否显示 loading 状态和图标，默认 false */
    showExpandLoading?: boolean;
    // ==================== 虚拟滚动配置 ====================
    /** 是否启用虚拟滚动（大数据量时建议开启） */
    virtual?: boolean;
    /** 虚拟滚动行高估算值（像素），默认根据 size 自动计算 */
    virtualRowHeight?: number;
    /** 虚拟滚动过扫描行数，默认 5 */
    virtualOverscan?: number;
}

const props = withDefaults(defineProps<Props>(), {
    columns: () => [],
    dataSource: () => [],
    rowKey: "id",
    bordered: false,
    size: "middle",
    loading: false,
    pagination: () => ({ current: 1, pageSize: 10, total: 0, showPagination: true }),
    minHeight: undefined,
    maxHeight: undefined,
    emptyText: undefined,
    showHeader: true,
    stripe: false,
    // 树形表格默认值
    treeProps: () => ({ children: "children", hasChildren: "hasChildren" }),
    expandRowByClick: false,
    indent: 30,
    showExpandLoading: false,
    // 虚拟滚动默认值
    virtual: false,
    virtualRowHeight: undefined,
    virtualOverscan: 5
});

// ==================== Loading 最小显示时间处理 ====================
const MIN_LOADING_DURATION = 200; // 最小 loading 显示时间（毫秒）
const internalLoading = ref(props.loading);
let loadingStartTime = 0;
let loadingTimer: ReturnType<typeof setTimeout> | null = null;

watch(
    () => props.loading,
    (newLoading) => {
        if (newLoading) {
            // loading 开始，记录开始时间并立即显示
            loadingStartTime = Date.now();
            if (loadingTimer) {
                clearTimeout(loadingTimer);
                loadingTimer = null;
            }
            internalLoading.value = true;
        } else {
            // loading 结束，确保至少显示 MIN_LOADING_DURATION 毫秒
            const elapsed = Date.now() - loadingStartTime;
            const remaining = MIN_LOADING_DURATION - elapsed;

            if (remaining > 0) {
                loadingTimer = setTimeout(() => {
                    internalLoading.value = false;
                    loadingTimer = null;
                }, remaining);
            } else {
                internalLoading.value = false;
            }
        }
    },
    { immediate: true }
);

onUnmounted(() => {
    if (loadingTimer) {
        clearTimeout(loadingTimer);
    }
});

const emit = defineEmits<{
    /** 分页、排序、筛选变化时触发 */
    change: [pagination: { current: number; pageSize: number }, filters: Record<string, any>, sorter: { field: string; order: "ascend" | "descend" | null }];
    /** 行展开变化时触发 */
    expand: [expanded: boolean, record: any];
    /** 展开行 keys 变化时触发 */
    "update:expandedRowKeys": [keys: (string | number)[]];
    /** 行选择变化时触发 */
    "update:selectedRowKeys": [keys: (string | number)[]];
}>();

// ==================== 子组件列配置收集 ====================
// 存储通过 TableColumn 子组件注册的列配置
const childColumns = ref<TableColumn[]>([]);
// slot 容器引用，用于获取 TableColumn 的 DOM 顺序
const slotContainerRef = ref<HTMLElement | null>(null);

// 根据 DOM 顺序排序列（修复 v-if 动态显隐导致的列顺序错乱问题）
const sortColumnsByDom = () => {
    if (!slotContainerRef.value) return;

    // 获取所有 column 锚点元素
    const anchors = slotContainerRef.value.querySelectorAll("[data-vort-column-uid]");

    // 只保留“顶层列”的锚点（排除嵌套在其他列里的子列）
    const topLevelAnchors = Array.from(anchors).filter((el) => {
        let parent = el.parentElement;
        while (parent && parent !== slotContainerRef.value) {
            if (parent.hasAttribute("data-vort-column-uid")) return false;
            parent = parent.parentElement;
        }
        return true;
    });

    const uidOrder = topLevelAnchors.map((el) => el.getAttribute("data-vort-column-uid"));
    const uidSet = new Set(uidOrder.filter(Boolean) as string[]);

    // 防御：避免嵌套子列误注册到 Table，导致在表格末尾重复出现
    childColumns.value = childColumns.value.filter((col) => !!col._uid && uidSet.has(col._uid));

    // 根据 DOM 顺序重新排序 childColumns
    childColumns.value.sort((a, b) => {
        const aIndex = uidOrder.indexOf(a._uid || "");
        const bIndex = uidOrder.indexOf(b._uid || "");
        // 如果找不到索引，放到最后
        if (aIndex === -1) return 1;
        if (bIndex === -1) return -1;
        return aIndex - bIndex;
    });
};

// 注册列（由 TableColumn 子组件调用）
const registerColumn = (column: TableColumn) => {
    // 使用 nextTick 确保所有子组件都挂载后再处理顺序
    nextTick(() => {
        const index = childColumns.value.findIndex((col) => col._uid === column._uid);
        if (index === -1) {
            childColumns.value.push(column);
        } else {
            childColumns.value[index] = column;
        }
        // 注册后根据 DOM 顺序重新排序
        sortColumnsByDom();
    });
};

// 注销列（由 TableColumn 子组件调用）
const unregisterColumn = (uid: string) => {
    const index = childColumns.value.findIndex((col) => col._uid === uid);
    if (index !== -1) {
        childColumns.value.splice(index, 1);
    }
};

// 提供上下文给子组件
provide<TableContext>(TABLE_INJECTION_KEY, {
    registerColumn,
    unregisterColumn
});

// 合并后的最终列配置（props.columns 优先，如果没有则使用子组件收集的列）
const mergedColumns = computed<TableColumn[]>(() => {
    // 如果 props.columns 有值，优先使用
    if (props.columns && props.columns.length > 0) {
        return props.columns;
    }
    // 否则使用子组件收集的列
    return childColumns.value;
});

// ==================== 多级表头支持 ====================
// 判断列是否有子列（多级表头）
const hasChildren = (column: TableColumn): boolean => {
    return Array.isArray(column.children) && column.children.length > 0;
};

// 计算表头最大深度
const getHeaderDepth = (columns: TableColumn[]): number => {
    let maxDepth = 1;
    for (const column of columns) {
        if (hasChildren(column)) {
            const childDepth = getHeaderDepth(column.children!) + 1;
            maxDepth = Math.max(maxDepth, childDepth);
        }
    }
    return maxDepth;
};

// 计算列的 colSpan（跨越的列数）
const getColSpan = (column: TableColumn): number => {
    if (!hasChildren(column)) {
        return 1;
    }
    return column.children!.reduce((sum, child) => sum + getColSpan(child), 0);
};

// 将列按层级分组（用于渲染多行表头）
interface HeaderCell {
    column: TableColumn;
    colSpan: number;
    rowSpan: number;
}

const getHeaderRows = computed<HeaderCell[][]>(() => {
    const columns = mergedColumns.value;
    const maxDepth = getHeaderDepth(columns);
    const rows: HeaderCell[][] = [];

    // 初始化每行的数组
    for (let i = 0; i < maxDepth; i++) {
        rows.push([]);
    }

    // 递归收集每层的表头单元格
    const collectCells = (cols: TableColumn[], depth: number) => {
        for (const column of cols) {
            const colSpan = getColSpan(column);
            const isLeaf = !hasChildren(column);
            // 叶子节点：rowSpan = maxDepth - depth；非叶子节点：rowSpan = 1
            const rowSpan = isLeaf ? maxDepth - depth : 1;

            rows[depth]!.push({
                column,
                colSpan,
                rowSpan
            });

            // 如果有子列，递归处理
            if (hasChildren(column)) {
                collectCells(column.children!, depth + 1);
            }
        }
    };

    collectCells(columns, 0);
    return rows;
});

// 获取所有叶子列（用于渲染表体）
const getLeafColumns = (columns: TableColumn[]): TableColumn[] => {
    const leaves: TableColumn[] = [];
    const collect = (cols: TableColumn[]) => {
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

const leafColumns = computed<TableColumn[]>(() => {
    return getLeafColumns(mergedColumns.value);
});

// 是否使用多级表头
const isMultiLevelHeader = computed(() => {
    return getHeaderDepth(mergedColumns.value) > 1;
});

// ==================== 内部分页状态 ====================
// 内部分页状态
const internalCurrent = ref(typeof props.pagination === "object" ? props.pagination.current || 1 : 1);
const internalPageSize = ref(typeof props.pagination === "object" ? props.pagination.pageSize || 10 : 10);

// 排序状态
const sortState = ref<SortState>({ field: "", order: null });

// ==================== 树形展开状态管理 ====================
// 展开的行 keys
const internalExpandedKeys = ref<Set<string | number>>(new Set(props.defaultExpandedRowKeys || props.expandedRowKeys || []));

// 树形节点状态（loading, loaded 等）
const treeNodeStates = reactive<Map<string | number, TreeNodeState>>(new Map());

// 懒加载的子节点数据
const lazyLoadedChildren = reactive<Map<string | number, any[]>>(new Map());

// 监听外部 expandedRowKeys 变化
watch(
    () => props.expandedRowKeys,
    (newKeys) => {
        if (newKeys !== undefined) {
            internalExpandedKeys.value = new Set(newKeys);
        }
    }
);

// 获取树形配置
const treeConfig = computed(() => ({
    childrenField: props.treeProps?.children || "children",
    hasChildrenField: props.treeProps?.hasChildren || "hasChildren"
}));

// 判断行是否有子节点
const rowHasChildren = (record: any): boolean => {
    const { childrenField, hasChildrenField } = treeConfig.value;
    // 优先检查 hasChildren 字段
    if (record[hasChildrenField] !== undefined) {
        return !!record[hasChildrenField];
    }
    // 其次检查 children 数组
    const children = record[childrenField];
    return Array.isArray(children) && children.length > 0;
};

// 获取行的子节点（包括懒加载的）
const getRowChildren = (record: any): any[] => {
    const key = getRowKey(record, 0);
    // 优先返回懒加载的数据
    if (lazyLoadedChildren.has(key)) {
        return lazyLoadedChildren.get(key) || [];
    }
    // 否则返回原始数据中的 children
    const { childrenField } = treeConfig.value;
    return record[childrenField] || [];
};

// 判断行是否展开
const isRowExpanded = (record: any, index: number): boolean => {
    const key = getRowKey(record, index);
    return internalExpandedKeys.value.has(key);
};

// 获取节点状态
const getTreeNodeState = (key: string | number): TreeNodeState => {
    if (!treeNodeStates.has(key)) {
        treeNodeStates.set(key, {
            expanded: false,
            loading: false,
            loaded: false,
            level: 0
        });
    }
    return treeNodeStates.get(key)!;
};

// 展开/折叠行
const toggleRowExpand = async (record: any, index: number) => {
    const key = getRowKey(record, index);
    const isExpanded = internalExpandedKeys.value.has(key);
    const nodeState = getTreeNodeState(key);

    if (isExpanded) {
        // 折叠
        internalExpandedKeys.value.delete(key);
    } else {
        // 展开
        internalExpandedKeys.value.add(key);

        // 如果有 loadChildren 且未加载过，则懒加载子节点
        if (props.loadChildren && !nodeState.loaded) {
            nodeState.loading = true;
            try {
                const children = await props.loadChildren(record);
                lazyLoadedChildren.set(key, children);
                nodeState.loaded = true;
            } catch (error) {
                console.error("[VortTable] 加载子节点失败:", error);
                internalExpandedKeys.value.delete(key); // 加载失败时取消展开
            } finally {
                nodeState.loading = false;
            }
        }
    }

    // 触发 v-model 更新
    emit("update:expandedRowKeys", [...internalExpandedKeys.value]);
    emit("expand", !isExpanded, record);
};

// 刷新指定节点的子节点
const refreshChildren = async (parentKey: string | number) => {
    // 找到对应的行数据
    const findRecord = (data: any[], key: string | number): any => {
        for (const record of data) {
            const recordKey = getRowKey(record, 0);
            if (recordKey === key) {
                return record;
            }
            const { childrenField } = treeConfig.value;
            const children = record[childrenField] || lazyLoadedChildren.get(recordKey);
            if (children?.length) {
                const found = findRecord(children, key);
                if (found) return found;
            }
        }
        return null;
    };

    const record = findRecord(props.dataSource || [], parentKey);
    if (!record || !props.loadChildren) return;

    const nodeState = getTreeNodeState(parentKey);
    nodeState.loading = true;

    try {
        const children = await props.loadChildren(record);
        lazyLoadedChildren.set(parentKey, children);
        nodeState.loaded = true;
    } catch (error) {
        console.error("[VortTable] 刷新子节点失败:", error);
    } finally {
        nodeState.loading = false;
    }
};

// 扁平化树形数据用于渲染
interface FlattenedRow {
    record: any;
    index: number;
    level: number;
    isLast: boolean;
    parentKey?: string | number;
}

const flattenTreeData = (data: any[], level: number = 0, parentKey?: string | number): FlattenedRow[] => {
    const result: FlattenedRow[] = [];

    data.forEach((record, index) => {
        const key = getRowKey(record, index);
        const isExpanded = internalExpandedKeys.value.has(key);
        const hasChildren = rowHasChildren(record);

        result.push({
            record,
            index,
            level,
            isLast: index === data.length - 1,
            parentKey
        });

        // 如果展开了，递归添加子节点
        if (isExpanded && hasChildren) {
            const children = getRowChildren(record);
            if (children.length > 0) {
                result.push(...flattenTreeData(children, level + 1, key));
            }
        }
    });

    return result;
};

// 初始化排序状态（根据 defaultSortOrder，使用叶子列因为只有叶子列可排序）
const initSortState = () => {
    for (const col of leafColumns.value) {
        if (col.sortOrder !== undefined) {
            sortState.value = { field: col.dataIndex || col.key || "", order: col.sortOrder };
            break;
        }
        if (col.defaultSortOrder) {
            sortState.value = { field: col.dataIndex || col.key || "", order: col.defaultSortOrder };
            break;
        }
    }
};

// 监听叶子列配置变化，初始化/更新排序状态
watch(
    leafColumns,
    () => {
        // 检查是否有受控的 sortOrder
        for (const col of leafColumns.value) {
            if (col.sortOrder !== undefined) {
                sortState.value = { field: col.dataIndex || col.key || "", order: col.sortOrder };
                return;
            }
        }
        // 如果当前没有排序状态，检查 defaultSortOrder
        if (!sortState.value.field) {
            initSortState();
        }
    },
    { deep: true, immediate: true }
);

// 监听外部分页变化
watch(
    () => props.pagination,
    (newVal) => {
        if (typeof newVal === "object") {
            if (newVal.current !== undefined) internalCurrent.value = newVal.current;
            if (newVal.pageSize !== undefined) internalPageSize.value = newVal.pageSize;
        }
    },
    { deep: true }
);

// 选中的行 keys
const selectedRowKeys = ref<(string | number)[]>(props.rowSelection?.selectedRowKeys || []);

// 监听外部选择变化
watch(
    () => props.rowSelection?.selectedRowKeys,
    (newVal) => {
        if (newVal !== undefined) {
            selectedRowKeys.value = newVal;
        }
    }
);

// 获取行的 key
const getRowKey = (record: any, index: number): string | number => {
    if (typeof props.rowKey === "function") {
        return props.rowKey(record);
    }
    return record[props.rowKey] ?? index;
};

// 排序后的数据
const sortedData = computed(() => {
    const data = [...(props.dataSource || [])];

    if (!sortState.value.field || !sortState.value.order) {
        return data;
    }

    // 查找排序列（使用叶子列因为只有叶子列可排序）
    const sortColumn = leafColumns.value.find((col) => (col.dataIndex || col.key) === sortState.value.field);

    if (!sortColumn?.sorter) {
        return data;
    }

    // "custom" 模式：后端排序，不进行前端排序
    if (sortColumn.sorter === "custom") {
        return data;
    }

    // 使用自定义排序函数或默认排序
    const sorterFn =
        typeof sortColumn.sorter === "function"
            ? sortColumn.sorter
            : (a: any, b: any) => {
                  const aVal = getCellValue(a, sortColumn);
                  const bVal = getCellValue(b, sortColumn);
                  if (aVal === bVal) return 0;
                  if (aVal === null || aVal === undefined) return 1;
                  if (bVal === null || bVal === undefined) return -1;
                  if (typeof aVal === "number" && typeof bVal === "number") {
                      return aVal - bVal;
                  }
                  return String(aVal).localeCompare(String(bVal));
              };

    return data.sort((a, b) => {
        const result = sorterFn(a, b);
        return sortState.value.order === "descend" ? -result : result;
    });
});

// 分页后的数据（如果前端分页）
const paginatedData = computed(() => {
    const data = sortedData.value;

    // 如果关闭分页或数据为空，返回原数据
    if (props.pagination === false || data.length === 0) {
        return data;
    }

    const pagination = props.pagination;

    // 判断是否后端分页：如果 total > 0 且 data.length < total，说明数据已被后端分页
    // 否则进行前端分页
    const isBackendPagination = pagination.total !== undefined && pagination.total > 0 && data.length < pagination.total;

    if (isBackendPagination) {
        return data;
    }

    // 前端分页
    const start = (internalCurrent.value - 1) * internalPageSize.value;
    const end = start + internalPageSize.value;
    return data.slice(start, end);
});

// 判断是否启用树形模式
const isTreeMode = computed(() => {
    return !!props.loadChildren || props.dataSource?.some((row) => rowHasChildren(row));
});

// 扁平化后的渲染数据（包含层级信息）
const flattenedRenderData = computed<FlattenedRow[]>(() => {
    if (!isTreeMode.value) {
        // 非树形模式，直接包装成 FlattenedRow 格式
        return paginatedData.value.map((record, index) => ({
            record,
            index,
            level: 0,
            isLast: index === paginatedData.value.length - 1
        }));
    }
    // 树形模式，扁平化数据
    return flattenTreeData(paginatedData.value);
});

// ==================== 虚拟滚动配置 ====================
// 根据 size 计算默认行高
const defaultRowHeight = computed(() => {
    if (props.virtualRowHeight) return props.virtualRowHeight;
    // 根据 size prop 返回不同的默认行高
    const sizeMap = {
        large: 57, // padding 20px * 2 + line-height ~17px
        middle: 49, // padding 16px * 2 + line-height ~17px
        small: 33 // padding 8px * 2 + line-height ~17px
    };
    return sizeMap[props.size] || sizeMap.middle;
});

// 是否启用虚拟滚动
const isVirtualEnabled = computed(() => {
    // 必须同时满足：开启 virtual prop 且有 scroll.y 固定高度
    return !!(props.virtual && props.scroll?.y);
});

// 总数据条数
const totalCount = computed(() => {
    if (props.pagination === false) return 0;
    const pagination = props.pagination;
    if (pagination.total !== undefined && pagination.total > 0) {
        return pagination.total;
    }
    return props.dataSource?.length || 0;
});

// 总页数
const totalPages = computed(() => {
    return Math.ceil(totalCount.value / internalPageSize.value);
});

// 分页配置
const paginationConfig = computed(() => {
    if (props.pagination === false) return null;

    return {
        current: internalCurrent.value,
        pageSize: internalPageSize.value,
        total: totalCount.value,
        showPagination: props.pagination.showPagination !== false,
        showSizeChanger: props.pagination.showSizeChanger ?? false,
        showQuickJumper: props.pagination.showQuickJumper ?? false,
        showTotal: props.pagination.showTotal ?? false,
        pageSizeOptions: props.pagination.pageSizeOptions ?? [10, 20, 50, 100]
    };
});

// 页码变化
const handlePageChange = (page: number) => {
    internalCurrent.value = page;
    emit("change", { current: page, pageSize: internalPageSize.value }, {}, sortState.value);
};

// 每页条数变化
const handlePageSizeChange = (size: number) => {
    internalPageSize.value = size;
    internalCurrent.value = 1;
    emit("change", { current: 1, pageSize: size }, {}, sortState.value);
};

// 排序处理
const handleSort = (column: TableColumn) => {
    if (!column.sorter) return;

    const field = column.dataIndex || column.key || "";
    let newOrder: "ascend" | "descend" | null;

    // 切换排序状态：无 -> 升序 -> 降序 -> 无
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

    // 排序后重置到第一页
    internalCurrent.value = 1;

    emit("change", { current: 1, pageSize: internalPageSize.value }, {}, { field, order: newOrder });
};

// 获取列的排序状态
const getColumnSortOrder = (column: TableColumn): "ascend" | "descend" | null => {
    const field = column.dataIndex || column.key || "";
    if (sortState.value.field === field) {
        return sortState.value.order;
    }
    return null;
};

// 全选状态
const isAllSelected = computed(() => {
    if (!props.rowSelection || paginatedData.value.length === 0) return false;
    let hasEnabled = false;
    for (let index = 0; index < paginatedData.value.length; index++) {
        const record = paginatedData.value[index];
        const checkboxProps = props.rowSelection?.getCheckboxProps?.(record);
        if (checkboxProps?.disabled) continue;
        hasEnabled = true;
        const key = getRowKey(record, index);
        if (!selectedRowKeys.value.includes(key)) return false;
    }
    // 没有任何可选行时，不应视为“全选”
    return hasEnabled;
});

// 全选框是否应禁用：当前页没有任何可选行
const isSelectAllDisabled = computed(() => {
    if (!props.rowSelection || paginatedData.value.length === 0) return true;
    return paginatedData.value.every((record) => {
        const checkboxProps = props.rowSelection?.getCheckboxProps?.(record);
        return !!checkboxProps?.disabled;
    });
});

// 部分选中状态
const isIndeterminate = computed(() => {
    if (!props.rowSelection || paginatedData.value.length === 0) return false;
    const enabledRecords = paginatedData.value.filter((record) => {
        const checkboxProps = props.rowSelection?.getCheckboxProps?.(record);
        return !checkboxProps?.disabled;
    });
    if (enabledRecords.length === 0) return false;
    const selectedCount = enabledRecords.filter((record, index) => {
        const key = getRowKey(record, index);
        return selectedRowKeys.value.includes(key);
    }).length;
    return selectedCount > 0 && selectedCount < enabledRecords.length;
});

// 全选/取消全选
const handleSelectAll = (checked: boolean) => {
    const enabledRecords = paginatedData.value.filter((record) => {
        const checkboxProps = props.rowSelection?.getCheckboxProps?.(record);
        return !checkboxProps?.disabled;
    });

    let newSelectedKeys: (string | number)[];
    let selectedRows: any[];

    if (checked) {
        // 全选：添加所有未禁用的行
        const newKeys = enabledRecords.map((record, index) => getRowKey(record, index));
        newSelectedKeys = [...new Set([...selectedRowKeys.value, ...newKeys])];
        selectedRows = props.dataSource?.filter((record, index) => newSelectedKeys.includes(getRowKey(record, index))) || [];
    } else {
        // 取消全选：移除当前页的所有未禁用行
        const currentPageKeys = enabledRecords.map((record, index) => getRowKey(record, index));
        newSelectedKeys = selectedRowKeys.value.filter((key) => !currentPageKeys.includes(key));
        selectedRows = props.dataSource?.filter((record, index) => newSelectedKeys.includes(getRowKey(record, index))) || [];
    }

    selectedRowKeys.value = newSelectedKeys;
    emit("update:selectedRowKeys", newSelectedKeys);
    props.rowSelection?.onChange?.(newSelectedKeys, selectedRows);
    props.rowSelection?.onSelectAll?.(checked, selectedRows, enabledRecords);
};

// 单行选择
const handleSelect = (record: any, checked: boolean, index: number) => {
    const key = getRowKey(record, index);

    let newSelectedKeys: (string | number)[];

    if (props.rowSelection?.type === "radio") {
        newSelectedKeys = checked ? [key] : [];
    } else {
        if (checked) {
            newSelectedKeys = [...selectedRowKeys.value, key];
        } else {
            newSelectedKeys = selectedRowKeys.value.filter((k) => k !== key);
        }
    }

    selectedRowKeys.value = newSelectedKeys;

    const selectedRows = props.dataSource?.filter((r, i) => newSelectedKeys.includes(getRowKey(r, i))) || [];

    emit("update:selectedRowKeys", newSelectedKeys);
    props.rowSelection?.onChange?.(newSelectedKeys, selectedRows);
    props.rowSelection?.onSelect?.(record, checked, selectedRows);
};

// 行是否选中
const isRowSelected = (record: any, index: number): boolean => {
    const key = getRowKey(record, index);
    return selectedRowKeys.value.includes(key);
};

// 获取单元格值
const getCellValue = (record: any, column: TableColumn): any => {
    if (!column.dataIndex) return "";
    // 支持嵌套字段，如 "user.name"
    const keys = column.dataIndex.split(".");
    let value = record;
    for (const key of keys) {
        value = value?.[key];
    }
    return value;
};

// 获取行类名
const getRowClassName = (record: any, index: number): string => {
    if (!props.rowClassName) return "";
    if (typeof props.rowClassName === "function") {
        return props.rowClassName(record, index);
    }
    return props.rowClassName;
};

// 尺寸样式
const sizeClass = computed(() => {
    const sizes = {
        large: "vort-table-large",
        middle: "vort-table-middle",
        small: "vort-table-small"
    };
    return sizes[props.size];
});

// 容器样式
const containerClass = computed(() => {
    const classes = ["vort-table-container"];
    if (props.bordered) classes.push("vort-table-bordered");
    classes.push(sizeClass.value);
    if (props.stripe) classes.push("vort-table-stripe");
    if (props.scroll?.y) classes.push("vort-table-fixed-header");
    if (isVirtualEnabled.value) classes.push("vort-table-virtual");
    if (props.class) classes.push(props.class);
    return classes;
});

// 容器样式（含 CSS 变量控制阴影）
const containerStyle = computed(() => {
    const showLeftShadow = scrollState.value.hasScrollbar && !scrollState.value.isScrollLeft;
    const showRightShadow = scrollState.value.hasScrollbar && !scrollState.value.isScrollRight;

    return {
        "--vort-table-left-shadow": showLeftShadow ? "inset 10px 0 8px -8px rgba(0, 0, 0, 0.1)" : "none",
        "--vort-table-right-shadow": showRightShadow ? "inset -10px 0 8px -8px rgba(0, 0, 0, 0.1)" : "none"
    };
});

// 表格滚动样式
const scrollStyle = computed(() => {
    const style: Record<string, string> = {};

    if (props.scroll?.x) {
        style.overflowX = "auto";
    }

    const computedMaxHeight =
        props.maxHeight !== undefined
            ? typeof props.maxHeight === "number"
                ? `${props.maxHeight}px`
                : props.maxHeight
            : props.scroll?.y
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

// 表格宽度
const tableStyle = computed(() => {
    if (props.scroll?.x) {
        const width = typeof props.scroll.x === "number" ? `${props.scroll.x}px` : props.scroll.x;
        return {
            width,
            minWidth: "100%",
            tableLayout: "fixed" as const
        };
    }
    return {};
});

// 计算固定列的位置偏移（使用 leafColumns 确保多级表头时偏移计算正确）
const getFixedColumnStyle = (column: TableColumn, isHeader: boolean = false) => {
    if (!column.fixed) return {};

    const style: Record<string, string> = {
        position: "sticky",
        zIndex: isHeader ? "4" : "2"
    };

    // 只为表头设置背景色，表体的背景色由 CSS 控制
    if (isHeader) {
        style.background = "var(--vort-table-header-bg, #fafafa)";
    }

    // 计算 left 固定列的偏移
    if (column.fixed === "left") {
        let leftOffset = 0;

        // 如果有选择列且固定
        if (props.rowSelection?.fixed) {
            leftOffset += parseColumnWidth(props.rowSelection.columnWidth || "48px");
        }

        // 累加前面的 fixed left 列宽度（使用叶子列）
        for (const col of leafColumns.value) {
            if (col === column) break;
            if (col.fixed === "left") {
                leftOffset += parseColumnWidth(col.width || 0);
            }
        }

        style.left = `${leftOffset}px`;
    }

    // 计算 right 固定列的偏移
    if (column.fixed === "right") {
        let rightOffset = 0;

        // 从后往前累加 fixed right 列宽度（使用叶子列）
        const reversedColumns = [...leafColumns.value].reverse();
        for (const col of reversedColumns) {
            if (col === column) break;
            if (col.fixed === "right") {
                rightOffset += parseColumnWidth(col.width || 0);
            }
        }

        style.right = `${rightOffset}px`;
    }

    return style;
};

// 选择列固定样式
const getSelectionColumnStyle = (isHeader: boolean = false) => {
    if (!props.rowSelection?.fixed) return {};

    const style: Record<string, string> = {
        position: "sticky",
        left: "0px",
        zIndex: isHeader ? "4" : "2"
    };

    // 只为表头设置背景色，表体的背景色由 CSS 控制
    if (isHeader) {
        style.background = "var(--vort-table-header-bg, #fafafa)";
    }

    return style;
};

// 解析列宽度为数字
const parseColumnWidth = (width: number | string | undefined): number => {
    if (!width) return 100; // 默认宽度
    if (typeof width === "number") return width;
    const num = parseInt(width, 10);
    return isNaN(num) ? 100 : num;
};

// 获取 fixed-left 的最后一个列的 key（需要显示阴影，使用叶子列）
const lastFixedLeftColumnKey = computed(() => {
    const fixedLeftColumns = leafColumns.value.filter((col): col is TableColumn => !!col && col.fixed === "left");
    if (fixedLeftColumns.length === 0) return null;
    const lastCol = fixedLeftColumns[fixedLeftColumns.length - 1]!;
    return lastCol.key || lastCol.dataIndex || lastCol.title;
});

// 获取 fixed-right 的第一个列的 key（需要显示阴影，使用叶子列）
const firstFixedRightColumnKey = computed(() => {
    const fixedRightColumns = leafColumns.value.filter((col): col is TableColumn => !!col && col.fixed === "right");
    if (fixedRightColumns.length === 0) return null;
    const firstCol = fixedRightColumns[0]!;
    return firstCol.key || firstCol.dataIndex || firstCol.title;
});

// 判断列是否是 fixed 区域的边界列（需要显示阴影的列）
const isFixedBoundaryColumn = (column: TableColumn): boolean => {
    if (!column.fixed) return false;
    const colKey = column.key || column.dataIndex || column.title;
    if (column.fixed === "left") {
        return colKey === lastFixedLeftColumnKey.value;
    }
    if (column.fixed === "right") {
        return colKey === firstFixedRightColumnKey.value;
    }
    return false;
};

// 判断选择列是否是 fixed-left 的边界列
const isSelectionColumnFixedBoundary = computed(() => {
    // 如果选择列不是固定的，则不是边界
    if (!props.rowSelection?.fixed) return false;
    // 如果没有其他 fixed-left 列，选择列就是边界（使用叶子列检查）
    const hasOtherFixedLeftColumns = leafColumns.value.some((col) => col.fixed === "left");
    return !hasOtherFixedLeftColumns;
});

// 获取空数据文本
const emptyTextValue = computed(() => props.emptyText ?? t("empty_text"));

// ==================== 固定列滚动阴影检测 ====================
const tableWrapperRef = ref<HTMLElement | null>(null);

// ==================== 虚拟滚动（顶层调用 composable）====================
const {
    virtualRows: virtualRowsFromComposable,
    totalSize: virtualTotalSize,
    measureElement: measureVirtualElement
} = useVirtualScroll<FlattenedRow>({
    items: flattenedRenderData,
    containerRef: tableWrapperRef,
    estimateSize: defaultRowHeight.value,
    overscan: props.virtualOverscan,
    enabled: isVirtualEnabled,
    getItemKey: (index) => {
        const item = flattenedRenderData.value[index];
        return item ? getRowKey(item.record, item.index) : index;
    }
});

// 最终用于渲染的数据（虚拟滚动 or 普通）
const renderRows = computed(() => {
    if (isVirtualEnabled.value && virtualRowsFromComposable.value.length > 0) {
        return virtualRowsFromComposable.value;
    }
    // 非虚拟滚动模式，包装成相同格式
    return flattenedRenderData.value.map((item, index) => ({
        index,
        key: getRowKey(item.record, item.index),
        size: defaultRowHeight.value,
        start: index * defaultRowHeight.value,
        item
    }));
});

const scrollState = ref({
    isScrollLeft: true, // 是否滚动到了左边界（初始在左边界）
    isScrollRight: true, // 是否滚动到了右边界（初始假设没有滚动条）
    hasScrollbar: false // 是否有横向滚动条
});

// ==================== 表格包装器尺寸覆盖 ====================
// 用于覆盖主题中写死的 .vort-table-wrapper { min-height: 300px; } 等场景
const normalizeSizeValue = (value: number | string): string => {
    return typeof value === "number" ? `${value}px` : value;
};

const applyWrapperSizeOverride = () => {
    const wrapper = tableWrapperRef.value;
    if (!wrapper) return;

    if (props.minHeight !== undefined) {
        wrapper.style.setProperty("min-height", normalizeSizeValue(props.minHeight), "important");
    } else {
        wrapper.style.removeProperty("min-height");
    }

    if (props.maxHeight !== undefined) {
        wrapper.style.setProperty("max-height", normalizeSizeValue(props.maxHeight), "important");
    } else if (!props.scroll?.y) {
        // maxHeight 未传且没有使用 scroll.y 控制时，清理以避免残留
        wrapper.style.removeProperty("max-height");
    }
};

// 更新滚动状态
const updateScrollState = () => {
    const wrapper = tableWrapperRef.value;
    if (!wrapper) return;

    const { scrollLeft, scrollWidth, clientWidth } = wrapper;
    const hasScrollbar = scrollWidth > clientWidth;

    scrollState.value = {
        hasScrollbar,
        isScrollLeft: scrollLeft <= 1, // 容差处理
        isScrollRight: scrollLeft + clientWidth >= scrollWidth - 1 // -1 处理精度问题
    };
};

// 监听滚动事件
const handleTableScroll = () => {
    updateScrollState();
};

// 初始化和窗口大小变化时更新
let resizeObserver: ResizeObserver | null = null;

const initScrollObserver = () => {
    const wrapper = tableWrapperRef.value;
    if (!wrapper) return;

    updateScrollState();
    wrapper.addEventListener("scroll", handleTableScroll);

    // 使用 ResizeObserver 监听尺寸变化
    resizeObserver = new ResizeObserver(() => {
        updateScrollState();
    });
    resizeObserver.observe(wrapper);
};

onMounted(() => {
    // 等待 DOM 渲染完成后初始化
    nextTick(() => {
        initScrollObserver();
        applyWrapperSizeOverride();
    });
});

watch([() => props.minHeight, () => props.maxHeight, () => props.scroll?.y], () => {
    nextTick(applyWrapperSizeOverride);
});

// 数据或列变化时重新计算滚动状态
watch(
    [() => props.dataSource, leafColumns, () => props.scroll],
    () => {
        nextTick(updateScrollState);
    },
    { deep: true }
);

onUnmounted(() => {
    tableWrapperRef.value?.removeEventListener("scroll", handleTableScroll);
    resizeObserver?.disconnect();
});

// ==================== 暴露方法给外部使用 ====================
defineExpose({
    /** 刷新指定节点的子节点 */
    refreshChildren,
    /** 展开指定行 */
    expandRow: (key: string | number) => {
        internalExpandedKeys.value.add(key);
        emit("update:expandedRowKeys", [...internalExpandedKeys.value]);
    },
    /** 折叠指定行 */
    collapseRow: (key: string | number) => {
        internalExpandedKeys.value.delete(key);
        emit("update:expandedRowKeys", [...internalExpandedKeys.value]);
    },
    /** 获取展开的行 keys */
    getExpandedRowKeys: () => [...internalExpandedKeys.value]
});
</script>

<template>
    <div :class="containerClass" :style="containerStyle">
        <!-- 隐藏的插槽容器，用于渲染 TableColumn 子组件以收集列配置 -->
        <!-- ref 用于获取 TableColumn 的 DOM 顺序，修复 v-if 动态显隐导致的列顺序错乱 -->
        <div ref="slotContainerRef" v-show="false" aria-hidden="true">
            <slot></slot>
        </div>

        <!-- 加载遮罩 -->
        <Spin :spinning="internalLoading" class="vort-table-spin" />

        <!-- 表格主体 -->
        <div ref="tableWrapperRef" class="vort-table-wrapper" :style="scrollStyle">
            <table class="vort-table" :style="tableStyle">
                <colgroup>
                    <col
                        v-if="rowSelection"
                        :style="{
                            width: rowSelection.columnWidth || '48px'
                        }"
                    />
                    <col
                        v-for="column in leafColumns"
                        :key="column.key || column.dataIndex || column.title"
                        :style="{
                            width: column.width ? (typeof column.width === 'number' ? `${column.width}px` : column.width) : undefined
                        }"
                    />
                </colgroup>
                <!-- 表头 -->
                <thead v-if="showHeader" class="vort-table-thead">
                    <!-- 多级表头：多行渲染 -->
                    <template v-if="isMultiLevelHeader">
                        <tr v-for="(headerRow, rowIndex) in getHeaderRows" :key="rowIndex">
                            <!-- 选择列（只在第一行显示，rowSpan = 表头深度） -->
                            <th
                                v-if="rowSelection && rowIndex === 0"
                                class="vort-table-selection-column"
                                :class="[
                                    rowSelection.fixed && 'vort-table-cell-fixed vort-table-cell-fixed-left',
                                    isSelectionColumnFixedBoundary && 'vort-table-cell-fixed-boundary'
                                ]"
                                :style="{
                                    width: rowSelection.columnWidth || '48px',
                                    ...getSelectionColumnStyle(true)
                                }"
                                :rowspan="getHeaderRows.length"
                            >
                                <Checkbox
                                    v-if="rowSelection.type !== 'radio' && !rowSelection.hideSelectAll"
                                    :checked="isAllSelected"
                                    :indeterminate="isIndeterminate"
                                    :disabled="isSelectAllDisabled"
                                    @update:checked="handleSelectAll"
                                />
                            </th>
                            <!-- 数据列 -->
                            <th
                                v-for="cell in headerRow"
                                :key="cell.column.key || cell.column.dataIndex || cell.column.title"
                                :class="[
                                    'vort-table-cell',
                                    `vort-table-align-${cell.column.align || 'center'}`,
                                    cell.column.sorter && !hasChildren(cell.column) && 'vort-table-cell-sortable',
                                    cell.column.fixed && `vort-table-cell-fixed vort-table-cell-fixed-${cell.column.fixed}`,
                                    isFixedBoundaryColumn(cell.column) && 'vort-table-cell-fixed-boundary',
                                    cell.column.headerClassName
                                ]"
                                :style="{
                                    width: cell.column.width
                                        ? typeof cell.column.width === 'number'
                                            ? `${cell.column.width}px`
                                            : cell.column.width
                                        : undefined,
                                    ...getFixedColumnStyle(cell.column, true)
                                }"
                                :colspan="cell.colSpan > 1 ? cell.colSpan : undefined"
                                :rowspan="cell.rowSpan > 1 ? cell.rowSpan : undefined"
                                @click="cell.column.sorter && !hasChildren(cell.column) ? handleSort(cell.column) : undefined"
                            >
                                <div class="vort-table-column-header">
                                    <!-- 优先使用 TableColumn 子组件的 header 插槽 -->
                                    <template v-if="cell.column._renderHeader">
                                        <HeaderRenderer :render="cell.column._renderHeader" :column="cell.column" />
                                    </template>
                                    <!-- 否则使用传统的具名插槽 -->
                                    <slot v-else :name="`header-${cell.column.slot || cell.column.dataIndex}`" :column="cell.column">
                                        {{ cell.column.title }}
                                    </slot>
                                    <!-- 排序图标（只有叶子列才有排序） -->
                                    <span v-if="cell.column.sorter && !hasChildren(cell.column)" class="vort-table-column-sorter">
                                        <CaretUpFilled
                                            class="vort-table-sorter-icon vort-table-sorter-up"
                                            :class="{ active: getColumnSortOrder(cell.column) === 'ascend' }"
                                        />
                                        <CaretDownFilled
                                            class="vort-table-sorter-icon vort-table-sorter-down"
                                            :class="{ active: getColumnSortOrder(cell.column) === 'descend' }"
                                        />
                                    </span>
                                </div>
                            </th>
                        </tr>
                    </template>
                    <!-- 单级表头：单行渲染（原逻辑） -->
                    <tr v-else>
                        <!-- 选择列 -->
                        <th
                            v-if="rowSelection"
                            class="vort-table-selection-column"
                            :class="[
                                rowSelection.fixed && 'vort-table-cell-fixed vort-table-cell-fixed-left',
                                isSelectionColumnFixedBoundary && 'vort-table-cell-fixed-boundary'
                            ]"
                            :style="{
                                width: rowSelection.columnWidth || '48px',
                                ...getSelectionColumnStyle(true)
                            }"
                        >
                            <Checkbox
                                v-if="rowSelection.type !== 'radio' && !rowSelection.hideSelectAll"
                                :checked="isAllSelected"
                                :indeterminate="isIndeterminate"
                                :disabled="isSelectAllDisabled"
                                @update:checked="handleSelectAll"
                            />
                        </th>
                        <!-- 数据列 -->
                        <th
                            v-for="column in mergedColumns"
                            :key="column.key || column.dataIndex || column.title"
                            :class="[
                                'vort-table-cell',
                                `vort-table-align-${column.align || 'left'}`,
                                column.sorter && 'vort-table-cell-sortable',
                                column.fixed && `vort-table-cell-fixed vort-table-cell-fixed-${column.fixed}`,
                                isFixedBoundaryColumn(column) && 'vort-table-cell-fixed-boundary',
                                column.headerClassName
                            ]"
                            :style="{
                                width: column.width ? (typeof column.width === 'number' ? `${column.width}px` : column.width) : undefined,
                                ...getFixedColumnStyle(column, true)
                            }"
                            @click="column.sorter ? handleSort(column) : undefined"
                        >
                            <div class="vort-table-column-header">
                                <!-- 优先使用 TableColumn 子组件的 header 插槽 -->
                                <template v-if="column._renderHeader">
                                    <HeaderRenderer :render="column._renderHeader" :column="column" />
                                </template>
                                <!-- 否则使用传统的具名插槽 -->
                                <slot v-else :name="`header-${column.slot || column.dataIndex}`" :column="column">
                                    {{ column.title }}
                                </slot>
                                <!-- 排序图标 -->
                                <span v-if="column.sorter" class="vort-table-column-sorter">
                                    <CaretUpFilled
                                        class="vort-table-sorter-icon vort-table-sorter-up"
                                        :class="{ active: getColumnSortOrder(column) === 'ascend' }"
                                    />
                                    <CaretDownFilled
                                        class="vort-table-sorter-icon vort-table-sorter-down"
                                        :class="{ active: getColumnSortOrder(column) === 'descend' }"
                                    />
                                </span>
                            </div>
                        </th>
                    </tr>
                </thead>

                <!-- 表体 -->
                <tbody class="vort-table-tbody">
                    <!-- 空状态（loading 时不显示） -->
                    <tr v-if="flattenedRenderData.length === 0 && !internalLoading" class="vort-table-empty-row">
                        <td :colspan="(rowSelection ? 1 : 0) + leafColumns.length" class="vort-table-empty-cell">
                            <slot name="empty">
                                <div class="vort-table-empty">
                                    <EmptyOutlined class="vort-table-empty-icon" />
                                    <span class="vort-table-empty-text">{{ emptyTextValue }}</span>
                                </div>
                            </slot>
                        </td>
                    </tr>

                    <!-- 虚拟滚动模式：使用占位行撑高 + 绝对定位可见行 -->
                    <template v-if="isVirtualEnabled && flattenedRenderData.length > 0">
                        <!-- 占位行：撑开总高度 -->
                        <tr class="vort-table-virtual-placeholder" :style="{ height: `${virtualTotalSize}px` }">
                            <td :colspan="(rowSelection ? 1 : 0) + leafColumns.length"></td>
                        </tr>
                    </template>

                    <!-- 数据行（虚拟滚动模式使用 renderRows，普通模式使用 flattenedRenderData） -->
                    <tr
                        v-for="virtualRow in renderRows"
                        :key="virtualRow.key"
                        :ref="isVirtualEnabled ? (el) => measureVirtualElement(el as HTMLElement) : undefined"
                        :data-index="virtualRow.index"
                        :class="[
                            'vort-table-row',
                            isVirtualEnabled && 'vort-table-row-virtual',
                            isRowSelected(virtualRow.item.record, virtualRow.item.index) && 'vort-table-row-selected',
                            getRowClassName(virtualRow.item.record, virtualRow.item.index)
                        ]"
                        :style="
                            isVirtualEnabled
                                ? {
                                      position: 'absolute',
                                      top: 0,
                                      left: 0,
                                      width: '100%',
                                      height: `${virtualRow.size}px`,
                                      transform: `translateY(${virtualRow.start}px)`
                                  }
                                : undefined
                        "
                        @click="
                            expandRowByClick && rowHasChildren(virtualRow.item.record)
                                ? toggleRowExpand(virtualRow.item.record, virtualRow.item.index)
                                : undefined
                        "
                    >
                        <!-- 选择列 -->
                        <td
                            v-if="rowSelection"
                            class="vort-table-selection-column"
                            :class="[
                                rowSelection.fixed && 'vort-table-cell-fixed vort-table-cell-fixed-left',
                                isSelectionColumnFixedBoundary && 'vort-table-cell-fixed-boundary'
                            ]"
                            :style="getSelectionColumnStyle(false)"
                        >
                            <Checkbox
                                :checked="isRowSelected(virtualRow.item.record, virtualRow.item.index)"
                                :disabled="rowSelection.getCheckboxProps?.(virtualRow.item.record)?.disabled"
                                @update:checked="(checked: boolean) => handleSelect(virtualRow.item.record, checked, virtualRow.item.index)"
                            />
                        </td>
                        <!-- 数据列（使用 leafColumns 确保多级表头时渲染正确） -->
                        <td
                            v-for="(column, colIndex) in leafColumns"
                            :key="column.key || column.dataIndex || column.title"
                            :class="[
                                'vort-table-cell',
                                `vort-table-align-${column.align || 'left'}`,
                                column.ellipsis && 'vort-table-cell-ellipsis',
                                column.fixed && `vort-table-cell-fixed vort-table-cell-fixed-${column.fixed}`,
                                isFixedBoundaryColumn(column) && 'vort-table-cell-fixed-boundary',
                                column.className
                            ]"
                            :style="getFixedColumnStyle(column, false)"
                        >
                            <!-- 第一列添加树形展开功能 -->
                            <div
                                v-if="colIndex === 0 && isTreeMode"
                                class="vort-table-cell-tree-wrapper"
                                :style="{ paddingLeft: `${virtualRow.item.level * indent}px` }"
                            >
                                <!-- 展开/折叠图标 -->
                                <span
                                    v-if="rowHasChildren(virtualRow.item.record)"
                                    class="vort-table-tree-expand-icon"
                                    :class="{
                                        'vort-table-tree-expand-icon--expanded': isRowExpanded(virtualRow.item.record, virtualRow.item.index),
                                        'vort-table-tree-expand-icon--loading':
                                            showExpandLoading && getTreeNodeState(getRowKey(virtualRow.item.record, virtualRow.item.index)).loading
                                    }"
                                    @click.stop="toggleRowExpand(virtualRow.item.record, virtualRow.item.index)"
                                >
                                    <!-- 展开/折叠图标 - 始终存在以保持动画连续性 -->
                                    <span class="vort-table-tree-expand-btn"></span>
                                    <!-- Loading 图标 - 绝对定位覆盖在展开按钮上 -->
                                    <LoadingOutlined
                                        v-if="showExpandLoading && getTreeNodeState(getRowKey(virtualRow.item.record, virtualRow.item.index)).loading"
                                        class="vort-table-tree-loading-icon"
                                    />
                                </span>
                                <!-- 占位符（无子节点时） -->
                                <span v-else class="vort-table-tree-expand-placeholder"></span>

                                <!-- 单元格内容 -->
                                <span class="vort-table-tree-cell-content">
                                    <!-- 优先使用 TableColumn 子组件的 default 插槽 -->
                                    <template v-if="column._renderCell">
                                        <CellRenderer
                                            :render="column._renderCell"
                                            :value="getCellValue(virtualRow.item.record, column)"
                                            :row="virtualRow.item.record"
                                            :index="virtualRow.item.index"
                                            :column="column"
                                        />
                                    </template>
                                    <!-- 否则使用传统的具名插槽 -->
                                    <slot
                                        v-else
                                        :name="column.slot || column.dataIndex"
                                        :text="getCellValue(virtualRow.item.record, column)"
                                        :record="virtualRow.item.record"
                                        :index="virtualRow.item.index"
                                        :column="column"
                                    >
                                        {{ getCellValue(virtualRow.item.record, column) }}
                                    </slot>
                                </span>
                            </div>
                            <!-- 非第一列或非树形模式 -->
                            <template v-else>
                                <!-- 优先使用 TableColumn 子组件的 default 插槽 -->
                                <template v-if="column._renderCell">
                                    <CellRenderer
                                        :render="column._renderCell"
                                        :value="getCellValue(virtualRow.item.record, column)"
                                        :row="virtualRow.item.record"
                                        :index="virtualRow.item.index"
                                        :column="column"
                                    />
                                </template>
                                <!-- 否则使用传统的具名插槽 -->
                                <slot
                                    v-else
                                    :name="column.slot || column.dataIndex"
                                    :text="getCellValue(virtualRow.item.record, column)"
                                    :record="virtualRow.item.record"
                                    :index="virtualRow.item.index"
                                    :column="column"
                                >
                                    {{ getCellValue(virtualRow.item.record, column) }}
                                </slot>
                            </template>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- 分页 -->
        <div v-if="paginationConfig?.showPagination && totalCount > 0" class="vort-table-pagination">
            <Pagination
                :current="internalCurrent"
                :page-size="internalPageSize"
                :total="totalCount"
                :show-size-changer="paginationConfig.showSizeChanger"
                :show-quick-jumper="paginationConfig.showQuickJumper"
                :show-total-info="!!paginationConfig.showTotal"
                :page-size-options="paginationConfig.pageSizeOptions"
                @update:current="handlePageChange"
                @update:page-size="handlePageSizeChange"
            />
        </div>
    </div>
</template>

<style scoped>
.vort-table-container {
    position: relative;
    width: 100%;
    min-width: 0; /* 防止 flex/grid 子元素撑开 */
    max-width: 100%;
    overflow: hidden; /* 约束内部不撑开 */
    font-size: 14px;
    color: var(--vort-text);
    background: var(--vort-bg-elevated, #fff);
}
/* 加载遮罩（Spin 是子组件，class 在子组件根节点上，需使用 deep 才能命中） */
.vort-table-container :deep(.vort-table-spin) {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.6);
    z-index: 10;
}

/* spinner 距顶部固定偏移，但容器过矮时自动缩小偏移，避免看不见 */
.vort-table-container :deep(.vort-table-spin .vort-spin-spinning) {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    /* 期望偏移 120px；容器高度不足时，top 最大不超过 (100% - 80px)，确保 spinner 可见 */
    top: clamp(16px, 220px, calc(100% - 80px));
}

/* 表格包装器 - 滚动容器 */
.vort-table-wrapper {
    overflow-x: auto;
    overflow-y: hidden;
}

/* 表格 */
.vort-table {
    width: 100%;
    border-collapse: collapse;
    border-spacing: 0;
    table-layout: auto;
    line-height: 1.5;
}

/* 表头 */
.vort-table-thead {
    background: var(--vort-table-header-bg, #fafafa);
}

/* 固定表头 */
.vort-table-fixed-header .vort-table-thead {
    position: relative;
    z-index: 3;
}

.vort-table-fixed-header .vort-table-thead th {
    position: sticky;
    top: 0;
    z-index: 3;
    background: var(--vort-table-header-bg, #fafafa);
}

/* 表体 - 确保在固定表头下方 */
.vort-table-fixed-header .vort-table-tbody {
    position: relative;
    z-index: 1;
}

.vort-table-thead th {
    padding: 16px;
    font-weight: 600;
    text-align: left;
    border-bottom: 1px solid var(--vort-border-secondary, #f0f0f0);
    white-space: nowrap;
    color: var(--vort-text);
}

/* 可排序列 */
.vort-table-cell-sortable {
    cursor: pointer;
    user-select: none;
    transition: background-color 0.2s;
}

/* 表头内容布局 */
.vort-table-column-header {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

/* 排序图标容器 */
.vort-table-column-sorter {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    margin-left: 4px;
    line-height: 0;
}

/* 排序图标 */
.vort-table-sorter-icon {
    width: 10px;
    height: 10px;
    color: var(--vort-text-tertiary, #bfbfbf);
    transition: color 0.2s;
}

.vort-table-sorter-up {
    margin-bottom: -1px;
}

.vort-table-sorter-down {
    margin-top: -2px;
}

.vort-table-sorter-icon.active {
    color: var(--vort-primary);
}

/* 表体 */
.vort-table-tbody tr {
    transition: background-color 0.2s;
}

.vort-table-tbody tr:hover {
    background: var(--vort-table-header-bg, #fafafa);
}

.vort-table-tbody td {
    padding: 16px;
    border-bottom: 1px solid var(--vort-border-secondary, #f0f0f0);
    color: var(--vort-text);
}

/* 选中行 */
.vort-table-row-selected {
    background: var(--vort-primary-bg, #e6f4ff);
}

.vort-table-row-selected:hover {
    background: var(--vort-primary-bg-hover, #bae0ff) !important;
}

/* 选择列 */
.vort-table-selection-column {
    width: 48px;
    padding: 16px 12px !important;
}

/* 选择列表头居中（覆盖 .vort-table-thead th 的 text-align: left） */
.vort-table-thead th.vort-table-selection-column {
    text-align: center;
}

/* 选择列数据单元格居中 */
.vort-table-tbody td.vort-table-selection-column {
    text-align: center;
}

/* 对齐方式 */
.vort-table-thead th.vort-table-align-left {
    text-align: left;
}

.vort-table-thead th.vort-table-align-center {
    text-align: center;
}

.vort-table-thead th.vort-table-align-right {
    text-align: right;
}

.vort-table-align-left {
    text-align: left;
}

.vort-table-align-center {
    text-align: center;
}

.vort-table-align-right {
    text-align: right;
}

/* 省略文本 */
.vort-table-cell-ellipsis {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 200px;
}

/* 空状态 */
.vort-table-empty-row:hover {
    background: transparent;
}

.vort-table-empty-cell {
    padding: 48px 16px !important;
    background: #ffffff;
}

.vort-table-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
}

.vort-table-empty-icon {
    width: 64px;
    height: 64px;
    color: var(--vort-border, #d9d9d9);
}

.vort-table-empty-text {
    font-size: 14px;
}

/* 固定列 */
.vort-table-cell-fixed {
    position: sticky;
    z-index: 2;
    background: var(--vort-bg-elevated, #fff);
    transition: background-color 0.2s;
}

.vort-table-thead .vort-table-cell-fixed {
    z-index: 4;
    background: var(--vort-table-header-bg, #fafafa);
}

/* 固定列阴影效果 - 只在边界列显示，通过 CSS 变量控制 */
.vort-table-cell-fixed-left.vort-table-cell-fixed-boundary::after,
.vort-table-cell-fixed-right.vort-table-cell-fixed-boundary::before {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0px;
    width: 20px;
    pointer-events: none;
    transition: box-shadow 0.2s;
}

.vort-table-cell-fixed-left.vort-table-cell-fixed-boundary::after {
    right: -20px;
    box-shadow: var(--vort-table-left-shadow, none);
}

.vort-table-cell-fixed-right.vort-table-cell-fixed-boundary::before {
    left: -20px;
    box-shadow: var(--vort-table-right-shadow, none);
}

/* 表头固定列阴影 - 更高层级确保不被遮挡 */
.vort-table-thead .vort-table-cell-fixed-left.vort-table-cell-fixed-boundary::after,
.vort-table-thead .vort-table-cell-fixed-right.vort-table-cell-fixed-boundary::before {
    z-index: 1;
}

/* 固定列在行选中和悬停时的背景 */
.vort-table-row:hover .vort-table-cell-fixed {
    background: var(--vort-table-header-bg, #fafafa);
}

.vort-table-row-selected .vort-table-cell-fixed {
    background: var(--vort-primary-bg, #e6f4ff);
}

.vort-table-row-selected:hover .vort-table-cell-fixed {
    background: var(--vort-primary-bg-hover, #bae0ff);
}

/* 边框样式 */
.vort-table-bordered .vort-table-wrapper {
    border: 1px solid var(--vort-border-secondary, #f0f0f0);
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
}

.vort-table-bordered .vort-table-thead th,
.vort-table-bordered .vort-table-tbody td {
    border-right: 1px solid var(--vort-border-secondary, #f0f0f0);
}

.vort-table-bordered .vort-table-thead th:last-child,
.vort-table-bordered .vort-table-tbody td:last-child {
    border-right: none;
}

/* 斑马纹 */
.vort-table-stripe .vort-table-tbody tr:nth-child(even) {
    background: var(--vort-table-header-bg, #fafafa);
}

.vort-table-stripe .vort-table-tbody tr:nth-child(even):hover {
    background: #f5f5f5;
}

/* 尺寸变体 */
.vort-table-large .vort-table-thead th,
.vort-table-large .vort-table-tbody td {
    padding: 20px 16px;
}

.vort-table-middle .vort-table-thead th,
.vort-table-middle .vort-table-tbody td {
    padding: 16px;
}

.vort-table-small .vort-table-thead th,
.vort-table-small .vort-table-tbody td {
    padding: 8px 12px;
}

.vort-table-small {
    font-size: 13px;
}

/* 分页容器 */
.vort-table-pagination {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: 16px 0;
}

/* ==================== 树形表格样式 ==================== */
.vort-table-cell-tree-wrapper {
    display: inline-flex;
    align-items: center;
    width: 100%;
}

.vort-table-tree-expand-icon {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 17px;
    height: 17px;
    margin-right: 8px;
    cursor: pointer;
    user-select: none;
    flex-shrink: 0;
}

.vort-table-tree-expand-placeholder {
    display: inline-block;
    width: 17px;
    height: 17px;
    margin-right: 8px;
    flex-shrink: 0;
}

/* 展开/折叠按钮 - Ant Design 风格 */
.vort-table-tree-expand-btn {
    position: relative;
    display: inline-block;
    width: 17px;
    height: 17px;
    background: #fff;
    border: 1px solid #f0f0f0;
    border-radius: var(--vort-border-radius-sm, 4px);
    transition: all 0.2s;
}

.vort-table-tree-expand-btn::before,
.vort-table-tree-expand-btn::after {
    content: "";
    position: absolute;
    background: currentColor;
    transition: transform 0.3s ease-out;
}

/* 横线 */
.vort-table-tree-expand-btn::before {
    top: 7px;
    left: 3px;
    right: 3px;
    height: 1px;
    transform: rotate(-180deg);
}

/* 竖线 */
.vort-table-tree-expand-btn::after {
    top: 3px;
    bottom: 3px;
    left: 7px;
    width: 1px;
    transform: rotate(0deg);
}

/* 展开状态 - 竖线旋转90度与横线重合，形成减号 */
.vort-table-tree-expand-icon--expanded .vort-table-tree-expand-btn::before {
    transform: rotate(0deg);
}

.vort-table-tree-expand-icon--expanded .vort-table-tree-expand-btn::after {
    transform: rotate(90deg);
}

/* Hover 效果 */
.vort-table-tree-expand-icon:hover .vort-table-tree-expand-btn {
    border-color: var(--vort-primary);
    color: var(--vort-primary);
}

/* Loading 图标 - 绝对定位覆盖在展开按钮上 */
.vort-table-tree-loading-icon {
    position: absolute;
    top: 0;
    left: 0;
    width: 17px;
    height: 17px;
    padding: 2px;
    box-sizing: border-box;
    color: var(--vort-primary);
    animation: vort-table-tree-spin 1s linear infinite;
    z-index: 1;
}

/* Loading 状态时隐藏展开按钮的图标线条 */
.vort-table-tree-expand-icon--loading .vort-table-tree-expand-btn::before,
.vort-table-tree-expand-icon--loading .vort-table-tree-expand-btn::after {
    opacity: 0;
}

@keyframes vort-table-tree-spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}

/* 单元格内容 */
.vort-table-tree-cell-content {
    flex: 1;
    min-width: 0;
    overflow: hidden;
}

/* 可点击展开的行 */
.vort-table-row[style*="cursor: pointer"]:hover {
    cursor: pointer;
}

/* ==================== 虚拟滚动样式 ==================== */
/* 虚拟滚动占位行 - 用于撑开总高度 */
.vort-table-virtual-placeholder {
    position: relative;
    visibility: hidden;
    pointer-events: none;
}

.vort-table-virtual-placeholder td {
    padding: 0 !important;
    border: none !important;
}

/* 虚拟滚动模式下的 tbody 需要相对定位 */
.vort-table-container.vort-table-virtual .vort-table-tbody {
    position: relative;
}

/* 虚拟滚动行 - 绝对定位 */
.vort-table-row-virtual {
    display: table-row;
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
}

/* 确保虚拟滚动行内的单元格正确显示 */
.vort-table-row-virtual td {
    display: table-cell;
}
</style>

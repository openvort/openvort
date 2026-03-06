/**
 * useTableSelection - 表格行选择 composable
 */
import { ref, computed, watch, type Ref, type ComputedRef } from "vue";
import type { TableRowSelection } from "../types";

export interface UseTableSelectionOptions<T = any> {
    /** 数据源 */
    dataSource: Ref<T[]> | ComputedRef<T[]>;
    /** 分页后的数据（用于当前页全选） */
    paginatedData: Ref<T[]> | ComputedRef<T[]>;
    /** 行选择配置 */
    rowSelection: Ref<TableRowSelection<T> | undefined> | ComputedRef<TableRowSelection<T> | undefined>;
    /** 获取行 key 的函数 */
    getRowKey: (record: T, index: number) => string | number;
    /** 选中行变化时的回调 */
    onSelectedRowKeysChange?: (keys: (string | number)[]) => void;
}

export interface UseTableSelectionReturn<T = any> {
    /** 选中的行 keys */
    selectedRowKeys: Ref<(string | number)[]>;
    /** 是否全选 */
    isAllSelected: ComputedRef<boolean>;
    /** 全选框是否禁用 */
    isSelectAllDisabled: ComputedRef<boolean>;
    /** 是否部分选中（indeterminate 状态） */
    isIndeterminate: ComputedRef<boolean>;
    /** 全选/取消全选处理 */
    handleSelectAll: (checked: boolean) => void;
    /** 单行选择处理 */
    handleSelect: (record: T, checked: boolean, index: number) => void;
    /** 判断行是否选中 */
    isRowSelected: (record: T, index: number) => boolean;
}

export function useTableSelection<T = any>(options: UseTableSelectionOptions<T>): UseTableSelectionReturn<T> {
    const { dataSource, paginatedData, rowSelection, getRowKey, onSelectedRowKeysChange } = options;

    // 选中的行 keys
    const selectedRowKeys = ref<(string | number)[]>(rowSelection.value?.selectedRowKeys || []);

    // 监听外部选择变化
    watch(
        () => rowSelection.value?.selectedRowKeys,
        (newVal) => {
            if (newVal !== undefined) {
                selectedRowKeys.value = newVal;
            }
        }
    );

    // 全选状态
    const isAllSelected = computed(() => {
        if (!rowSelection.value || paginatedData.value.length === 0) return false;
        let hasEnabled = false;
        for (let index = 0; index < paginatedData.value.length; index++) {
            const record = paginatedData.value[index]!;
            const checkboxProps = rowSelection.value?.getCheckboxProps?.(record);
            if (checkboxProps?.disabled) continue;
            hasEnabled = true;
            const key = getRowKey(record, index);
            if (!selectedRowKeys.value.includes(key)) return false;
        }
        // 没有任何可选行时，不应视为"全选"
        return hasEnabled;
    });

    // 全选框是否应禁用：当前页没有任何可选行
    const isSelectAllDisabled = computed(() => {
        if (!rowSelection.value || paginatedData.value.length === 0) return true;
        return paginatedData.value.every((record) => {
            const checkboxProps = rowSelection.value?.getCheckboxProps?.(record);
            return !!checkboxProps?.disabled;
        });
    });

    // 部分选中状态
    const isIndeterminate = computed(() => {
        if (!rowSelection.value || paginatedData.value.length === 0) return false;
        const enabledRecords = paginatedData.value.filter((record) => {
            const checkboxProps = rowSelection.value?.getCheckboxProps?.(record);
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
            const checkboxProps = rowSelection.value?.getCheckboxProps?.(record);
            return !checkboxProps?.disabled;
        });

        let newSelectedKeys: (string | number)[];
        let selectedRows: T[];

        if (checked) {
            // 全选：添加所有未禁用的行
            const newKeys = enabledRecords.map((record, index) => getRowKey(record, index));
            newSelectedKeys = [...new Set([...selectedRowKeys.value, ...newKeys])];
            selectedRows = dataSource.value.filter((record, index) => newSelectedKeys.includes(getRowKey(record, index)));
        } else {
            // 取消全选：移除当前页的所有未禁用行
            const currentPageKeys = enabledRecords.map((record, index) => getRowKey(record, index));
            newSelectedKeys = selectedRowKeys.value.filter((key) => !currentPageKeys.includes(key));
            selectedRows = dataSource.value.filter((record, index) => newSelectedKeys.includes(getRowKey(record, index)));
        }

        selectedRowKeys.value = newSelectedKeys;
        onSelectedRowKeysChange?.(newSelectedKeys);
        rowSelection.value?.onChange?.(newSelectedKeys, selectedRows);
        rowSelection.value?.onSelectAll?.(checked, selectedRows, enabledRecords);
    };

    // 单行选择
    const handleSelect = (record: T, checked: boolean, index: number) => {
        const key = getRowKey(record, index);

        let newSelectedKeys: (string | number)[];

        if (rowSelection.value?.type === "radio") {
            newSelectedKeys = checked ? [key] : [];
        } else {
            if (checked) {
                newSelectedKeys = [...selectedRowKeys.value, key];
            } else {
                newSelectedKeys = selectedRowKeys.value.filter((k) => k !== key);
            }
        }

        selectedRowKeys.value = newSelectedKeys;

        const selectedRows = dataSource.value.filter((r, i) => newSelectedKeys.includes(getRowKey(r, i)));

        onSelectedRowKeysChange?.(newSelectedKeys);
        rowSelection.value?.onChange?.(newSelectedKeys, selectedRows);
        rowSelection.value?.onSelect?.(record, checked, selectedRows);
    };

    // 行是否选中
    const isRowSelected = (record: T, index: number): boolean => {
        const key = getRowKey(record, index);
        return selectedRowKeys.value.includes(key);
    };

    return {
        selectedRowKeys,
        isAllSelected,
        isSelectAllDisabled,
        isIndeterminate,
        handleSelectAll,
        handleSelect,
        isRowSelected
    };
}

export default useTableSelection;

import { ref, reactive, computed, unref } from "vue";
import type { ComputedRef, Ref } from "vue";
import { message } from "@/components/vort/message";

// ===================== 类型定义 =====================

type PaginatedResult<T> = { records: T[]; total: number };
type ApiFunction<T, P> = (params: P) => Promise<PaginatedResult<T>>;
type ReactiveApiFunction<T, P> = ApiFunction<T, P> | ComputedRef<ApiFunction<T, P>>;
type DeleteApi = (data: { id: string }) => Promise<any>;

interface CrudPageOptions<T, P> {
    api?: ReactiveApiFunction<T, P>;
    idKey?: keyof T & string;
    defaultParams?: Partial<P>;
    ignoreResetParams?: string[];
    deleteApi?: DeleteApi;
}

// ===================== Hook 实现 =====================

export function useCrudPage<T extends Record<string, any>, P extends { page?: number; size?: number } = { page: number; size: number }>(
    options: CrudPageOptions<T, P>
) {
    const listData = ref<T[]>([]) as Ref<T[]>;
    const loading = ref(false);
    const total = ref(0);
    const selectedIds = ref<string[]>([]);
    const idKey = options.idKey || ("id" as keyof T & string);
    const ignoreSet = new Set(options.ignoreResetParams || []);

    const initialParams = { page: 1, size: 20, sortField: "", sortOrder: "", ...options.defaultParams } as unknown as P;
    const filterParams = reactive<P>({ ...initialParams });

    const resolvedApi = computed<ApiFunction<T, P>>(() => {
        const fn = unref(options.api);
        return typeof fn === "function" ? fn : () => Promise.reject("API function is invalid");
    });

    const loadData = async () => {
        loading.value = true;
        try {
            if ("keyword" in filterParams) {
                const kw = (filterParams as Record<string, any>).keyword;
                if (typeof kw === "string") (filterParams as Record<string, any>).keyword = kw.trim();
            }
            const result = await resolvedApi.value(filterParams as P);
            listData.value = result.records;
            total.value = result.total;
        } catch (error: any) {
            message.error(error?.message || "请求失败");
        } finally {
            loading.value = false;
        }
    };

    const onSearchSubmit = () => {
        (filterParams as any).page = 1;
        loadData();
    };

    const resetParams = () => {
        Object.keys(initialParams).forEach((key) => {
            if (!ignoreSet.has(key)) (filterParams as any)[key] = (initialParams as any)[key];
        });
        Object.keys(filterParams as any).forEach((key) => {
            if (!(key in initialParams) && !ignoreSet.has(key)) delete (filterParams as any)[key];
        });
        loadData();
    };

    const onSortChange = (
        _pagination: any,
        _filters: any,
        sorter: { field?: string; order?: "ascend" | "descend" | null }
    ) => {
        (filterParams as any).sortField = sorter.field || "";
        (filterParams as any).sortOrder = sorter.order === "ascend" ? "asc" : sorter.order === "descend" ? "desc" : "";
        loadData();
    };

    const rowSelection = computed(() => ({
        selectedRowKeys: selectedIds.value as Array<string | number>,
        onChange: (_keys: Array<string | number>, selectedRows: T[]) => {
            selectedIds.value = selectedRows.map((item) => String(item[idKey]));
        }
    }));

    const hasSelection = computed(() => selectedIds.value.length > 0);
    const clearSelection = () => { selectedIds.value = []; };
    const showPagination = computed(() => total.value > 0);

    const deleteRow = async (row: T): Promise<boolean> => {
        if (!options.deleteApi) { message.error("未配置删除 API"); return false; }
        try {
            await options.deleteApi({ id: String(row[idKey]) });
            message.success("删除成功");
            loadData();
            return true;
        } catch (error: any) {
            message.error(error?.message || "删除失败");
            return false;
        }
    };

    return {
        listData, loading, total, filterParams,
        selectedIds, hasSelection, rowSelection, clearSelection,
        loadData, onSearchSubmit, resetParams, onSortChange,
        deleteRow, showPagination
    };
}

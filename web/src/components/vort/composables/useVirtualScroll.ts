/**
 * useVirtualScroll - 虚拟滚动 composable
 * 基于 @tanstack/vue-virtual 封装，用于 Table/Select 等组件
 */

import { ref, computed, type Ref, type ComputedRef, watch, onMounted, nextTick } from "vue";
import { useVirtualizer, type VirtualizerOptions } from "@tanstack/vue-virtual";

export interface UseVirtualScrollOptions<T = unknown> {
    /** 数据列表 */
    items: Ref<T[]> | ComputedRef<T[]>;
    /** 容器元素引用 */
    containerRef: Ref<HTMLElement | null>;
    /** 预估行高（像素） */
    estimateSize?: number;
    /** 过扫描行数（上下各多渲染几行，避免快速滚动时闪白） */
    overscan?: number;
    /** 是否启用 */
    enabled?: Ref<boolean> | ComputedRef<boolean> | boolean;
    /** 获取行 key 的函数 */
    getItemKey?: (index: number) => string | number;
}

export interface UseVirtualScrollReturn<T = unknown> {
    /** 虚拟滚动器实例 */
    virtualizer: ReturnType<typeof useVirtualizer<HTMLElement, HTMLElement>>;
    /** 虚拟化的行列表 */
    virtualRows: ComputedRef<
        Array<{
            index: number;
            key: string | number;
            size: number;
            start: number;
            item: T;
        }>
    >;
    /** 总高度（用于撑开滚动容器） */
    totalSize: ComputedRef<number>;
    /** 是否正在虚拟滚动 */
    isVirtualizing: ComputedRef<boolean>;
    /** 滚动到指定索引 */
    scrollToIndex: (index: number, options?: { align?: "start" | "center" | "end" | "auto" }) => void;
    /** 滚动到指定偏移 */
    scrollToOffset: (offset: number) => void;
    /** 测量元素（当行高变化时调用） */
    measureElement: (element: HTMLElement | null) => void;
}

export function useVirtualScroll<T = unknown>(options: UseVirtualScrollOptions<T>): UseVirtualScrollReturn<T> {
    const { items, containerRef, estimateSize = 48, overscan = 5, enabled = true, getItemKey } = options;

    // 解析 enabled 为响应式值
    const isEnabled = computed(() => {
        if (typeof enabled === "boolean") return enabled;
        return enabled.value;
    });

    // 虚拟滚动器配置
    const virtualizerOptions = computed(() => ({
        count: items.value.length,
        getScrollElement: () => containerRef.value,
        estimateSize: () => estimateSize,
        overscan,
        getItemKey: getItemKey ?? ((index) => index)
    }));

    // 创建虚拟滚动器
    const virtualizer = useVirtualizer<HTMLElement, HTMLElement>(
        virtualizerOptions as Parameters<typeof useVirtualizer<HTMLElement, HTMLElement>>[0]
    );

    // 虚拟化的行
    const virtualRows = computed(() => {
        if (!isEnabled.value) {
            // 未启用虚拟滚动时，返回所有行
            return items.value.map((item, index) => ({
                index,
                key: getItemKey ? getItemKey(index) : index,
                size: estimateSize,
                start: index * estimateSize,
                item
            }));
        }

        return virtualizer.value.getVirtualItems().map((virtualRow) => ({
            index: virtualRow.index,
            key: typeof virtualRow.key === "bigint" ? Number(virtualRow.key) : (virtualRow.key as string | number),
            size: virtualRow.size,
            start: virtualRow.start,
            item: items.value[virtualRow.index] as T
        }));
    });

    // 总高度
    const totalSize = computed(() => {
        if (!isEnabled.value) {
            return items.value.length * estimateSize;
        }
        return virtualizer.value.getTotalSize();
    });

    // 是否正在虚拟滚动
    const isVirtualizing = computed(() => {
        return isEnabled.value && items.value.length > overscan * 2;
    });

    // 滚动到指定索引
    const scrollToIndex = (index: number, options?: { align?: "start" | "center" | "end" | "auto" }) => {
        virtualizer.value.scrollToIndex(index, options);
    };

    // 滚动到指定偏移
    const scrollToOffset = (offset: number) => {
        virtualizer.value.scrollToOffset(offset);
    };

    // 测量元素
    const measureElement = (element: HTMLElement | null) => {
        if (element) {
            virtualizer.value.measureElement(element);
        }
    };

    return {
        virtualizer,
        virtualRows,
        totalSize,
        isVirtualizing,
        scrollToIndex,
        scrollToOffset,
        measureElement
    };
}

export default useVirtualScroll;

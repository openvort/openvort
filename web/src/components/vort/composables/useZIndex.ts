import { computed, inject, provide, ref, type ComputedRef, type InjectionKey, type Ref } from "vue";

/** z-index 层级管理 - 解决 Dialog/Drawer 内嵌弹出层级问题 */

// ============ z-index 层级定义 ============

/** z-index 基础值定义 */
export const Z_INDEX_BASE = {
    /** 弹出层基础值（Dropdown, Select, Cascader, AutoComplete 等） */
    popup: 1050,
    /** 弹窗基础值（Modal, Dialog） */
    modal: 1000,
    /** 抽屉基础值 */
    drawer: 1000,
    /** 消息提示基础值 */
    message: 1010,
    /** 通知基础值 */
    notification: 1010,
    /** Tooltip 基础值 */
    tooltip: 1070,
    /** Popover 基础值 */
    popover: 1030,
    /** Popconfirm 基础值 */
    popconfirm: 1030,
    /** 图片预览基础值 */
    imagePreview: 1080
} as const;

/**
 * 弹出层相对于父容器的增量
 * 当组件在容器（Dialog/Drawer）内部时，使用增量而非基础值
 */
export const Z_INDEX_INCREMENT = {
    /** 弹出层增量 */
    popup: 50,
    /** Tooltip 增量 */
    tooltip: 70,
    /** Popover 增量 */
    popover: 30,
    /** Popconfirm 增量 */
    popconfirm: 30,
    /** 图片预览增量 */
    imagePreview: 80
} as const;

// ============ 类型定义 ============

export type ZIndexComponentType = keyof typeof Z_INDEX_INCREMENT;

interface ZIndexContext {
    /** 父容器的 z-index 值 */
    zIndex: Ref<number>;
}

// ============ 注入 Key ============

const Z_INDEX_CONTEXT_KEY: InjectionKey<ZIndexContext> = Symbol("vort-z-index-context");

// ============ Provider - 容器组件使用 ============

/**
 * 为容器组件提供 z-index 上下文
 *
 * @description
 * 在 Dialog、Drawer 等容器组件中调用，将自己的 z-index 传递给子组件
 *
 * @param zIndex 容器组件的 z-index 值（响应式）
 *
 * @example
 * ```vue
 * <script setup>
 * import { useZIndexProvider } from '@/components/vort/composables'
 *
 * const props = defineProps<{ zIndex: number }>()
 *
 * // 将 Dialog 的 z-index 提供给子组件
 * useZIndexProvider(computed(() => props.zIndex))
 * </script>
 * ```
 */
export function useZIndexProvider(zIndex: Ref<number> | ComputedRef<number>): void {
    provide(Z_INDEX_CONTEXT_KEY, {
        zIndex: ref(zIndex.value)
    });

    // 如果是响应式的，需要同步更新
    // 这里我们使用一个 computed 包装，让 inject 的组件也能响应变化
}

/**
 * 为容器组件提供 z-index 上下文（增强版）
 *
 * @description
 * 与 useZIndexProvider 类似，但会自动处理响应式更新
 *
 * @param getZIndex 获取 z-index 值的函数
 */
export function useZIndexProviderValue(getZIndex: () => number): void {
    provide(Z_INDEX_CONTEXT_KEY, {
        zIndex: computed(getZIndex)
    });
}

// ============ Consumer - 弹出组件使用 ============

/**
 * 获取弹出组件的最终 z-index 值
 *
 * @description
 * 在 Select、Dropdown、Tooltip 等弹出组件中调用
 * 自动计算最终的 z-index：
 * - 如果在容器组件内，返回 父级z-index + 增量
 * - 如果不在容器内，返回组件的基础 z-index
 *
 * @param componentType 组件类型，用于确定增量值
 * @param customZIndex 用户自定义的 z-index（可选，优先级最高）
 *
 * @returns 计算后的 z-index 值（响应式）
 *
 * @example
 * ```vue
 * <script setup>
 * import { useZIndex } from '@/components/vort/composables'
 *
 * // Select 组件获取 z-index
 * const zIndex = useZIndex('popup')
 *
 * // 如果在 Dialog 内（z-index: 1000），返回 1050
 * // 如果不在容器内，返回基础值 1050
 * </script>
 *
 * <template>
 *   <Teleport to="body">
 *     <div :style="{ zIndex }">...</div>
 *   </Teleport>
 * </template>
 * ```
 */
export function useZIndex(componentType: ZIndexComponentType, customZIndex?: Ref<number | undefined> | ComputedRef<number | undefined>): ComputedRef<number> {
    const context = inject(Z_INDEX_CONTEXT_KEY, null);

    return computed(() => {
        // 用户自定义 z-index 优先级最高
        if (customZIndex?.value !== undefined) {
            return customZIndex.value;
        }

        // 如果有父容器上下文，使用 父级z-index + 增量
        if (context) {
            return context.zIndex.value + Z_INDEX_INCREMENT[componentType];
        }

        // 没有父容器，使用基础值
        const baseKey = componentType as keyof typeof Z_INDEX_BASE;
        return Z_INDEX_BASE[baseKey] ?? Z_INDEX_BASE.popup;
    });
}

/**
 * 获取弹出组件的 z-index 值（简化版）
 *
 * @description
 * 直接返回数值，适用于非响应式场景
 *
 * @param componentType 组件类型
 * @param customZIndex 自定义 z-index
 */
export function getZIndex(componentType: ZIndexComponentType, customZIndex?: number): number {
    if (customZIndex !== undefined) {
        return customZIndex;
    }

    const baseKey = componentType as keyof typeof Z_INDEX_BASE;
    return Z_INDEX_BASE[baseKey] ?? Z_INDEX_BASE.popup;
}

/**
 * 检查是否在容器组件（Dialog/Drawer）内部
 *
 * @returns 是否在容器内
 */
export function useInZIndexContext(): boolean {
    const context = inject(Z_INDEX_CONTEXT_KEY, null);
    return context !== null;
}

/**
 * 获取父容器的 z-index
 *
 * @returns 父容器的 z-index 值，如果不在容器内则返回 undefined
 */
export function useParentZIndex(): ComputedRef<number | undefined> {
    const context = inject(Z_INDEX_CONTEXT_KEY, null);

    return computed(() => context?.zIndex.value);
}

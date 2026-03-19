<script lang="ts" generic="T = any">
// 导出类型
export interface TableColumnProps {
    /** 列数据字段名（对应 dataIndex） */
    prop?: string;
    /** 列标题（对应 title） */
    label?: string;
    /** 列宽度 */
    width?: number | string;
    /** 列对齐方式 */
    align?: "left" | "center" | "right";
    /** 是否固定列 */
    fixed?: "left" | "right";
    /** 单元格样式类名 */
    className?: string;
    /** 表头样式类名 */
    headerClassName?: string;
    /** 是否可排序 */
    sortable?: boolean | "custom";
    /** 自定义排序函数 */
    sortMethod?: (a: any, b: any) => number;
    /** 默认排序顺序 */
    defaultSort?: "ascend" | "descend";
    /** 是否省略超长内容 */
    ellipsis?: boolean;
}
</script>

<script setup lang="ts" generic="T = any">
import { inject, provide, onMounted, onUnmounted, useSlots, getCurrentInstance, watch, ref, nextTick } from "vue";
import type { TableColumn, TableCellScope, TableHeaderScope, TableColumnContext } from "./types";
import { TABLE_INJECTION_KEY, TABLE_COLUMN_INJECTION_KEY } from "./types";

defineOptions({ name: "VortTableColumn" });

/**
 * Vort TableColumn - Element Plus 风格的表格列组件
 *
 * 支持嵌套使用实现多级表头：
 * <vort-table :data-source="data">
 *     <vort-table-column prop="date" label="日期" />
 *     <vort-table-column label="配送信息">
 *         <vort-table-column prop="name" label="姓名" />
 *         <vort-table-column label="地址信息">
 *             <vort-table-column prop="state" label="省份" />
 *             <vort-table-column prop="city" label="城市" />
 *         </vort-table-column>
 *     </vort-table-column>
 * </vort-table>
 */

// 定义插槽类型
defineSlots<{
    /** 单元格内容插槽（叶子列使用）或嵌套子列（多级表头） */
    default?: (props: { value: any; row: T; index: number; column: TableColumn<T> }) => any;
    /** 表头内容插槽 */
    header?: (props: { column: TableColumn<T> }) => any;
}>();

const props = withDefaults(defineProps<TableColumnProps>(), {
    align: "left",
    ellipsis: false
});

const slots = useSlots();
const instance = getCurrentInstance();
const tableContext = inject(TABLE_INJECTION_KEY, null);
// 父级 TableColumn 上下文（如果存在说明是嵌套的子列）
const parentColumnContext = inject(TABLE_COLUMN_INJECTION_KEY, null);

/**
 * 兼容性兜底：如果由于 HMR / 重复模块实例导致 Symbol 不一致，inject 可能拿不到父级 TableColumn 上下文，
 * 从而把“子列”错误注册到 Table 上，表现为嵌套列在表格末尾重复出现。
 *
 * 这里通过遍历父链的 provides，按 Symbol.description 寻找同名上下文，确保嵌套列只注册到父列。
 */
const resolveParentColumnContextFallback = (): TableColumnContext | null => {
    // inject 成功则不需要兜底
    if (parentColumnContext) return parentColumnContext;
    if (!instance?.parent) return null;

    // 从父链向上查找 provides 中的 “VortTableColumn” 上下文
    let cur: any = instance.parent;
    while (cur) {
        const provides: any = cur.provides;
        if (provides) {
            const keys = Reflect.ownKeys(provides);
            for (const key of keys) {
                if (typeof key !== "symbol") continue;
                if (key.description !== "VortTableColumn") continue;
                const ctx = provides[key];
                if (ctx && typeof ctx.registerChildColumn === "function" && typeof ctx.unregisterChildColumn === "function") {
                    return ctx as TableColumnContext;
                }
            }
        }
        cur = cur.parent;
    }

    return null;
};

const resolvedParentColumnContext = ref<TableColumnContext | null>(parentColumnContext);

// 生成唯一 ID
const uid = `table-column-${instance?.uid || Math.random().toString(36).slice(2)}`;

// ==================== 子列收集（用于多级表头） ====================
const childColumns = ref<TableColumn[]>([]);
const slotContainerRef = ref<HTMLElement | null>(null);

// 根据 DOM 顺序排序子列
const sortChildColumnsByDom = () => {
    if (!slotContainerRef.value) return;

    const anchors = slotContainerRef.value.querySelectorAll("[data-vort-column-uid]");
    const uidOrder = Array.from(anchors).map((el) => el.getAttribute("data-vort-column-uid"));

    childColumns.value.sort((a, b) => {
        const aIndex = uidOrder.indexOf(a._uid || "");
        const bIndex = uidOrder.indexOf(b._uid || "");
        if (aIndex === -1) return 1;
        if (bIndex === -1) return -1;
        return aIndex - bIndex;
    });
};

// 注册子列
const registerChildColumn = (column: TableColumn) => {
    nextTick(() => {
        const index = childColumns.value.findIndex((col) => col._uid === column._uid);
        if (index === -1) {
            childColumns.value.push(column);
        } else {
            childColumns.value[index] = column;
        }
        sortChildColumnsByDom();
        // 子列变化后重新注册当前列
        registerColumnConfig();
    });
};

// 注销子列
const unregisterChildColumn = (childUid: string) => {
    const index = childColumns.value.findIndex((col) => col._uid === childUid);
    if (index !== -1) {
        childColumns.value.splice(index, 1);
        // 子列变化后重新注册当前列
        registerColumnConfig();
    }
};

// 提供上下文给嵌套的子 TableColumn
provide<TableColumnContext>(TABLE_COLUMN_INJECTION_KEY, {
    registerChildColumn,
    unregisterChildColumn
});

// ==================== 构建列配置 ====================
const buildColumnConfig = (): TableColumn => {
    const config: TableColumn = {
        _uid: uid,
        key: props.prop || uid,
        dataIndex: props.prop,
        title: props.label,
        width: props.width,
        align: props.align,
        fixed: props.fixed,
        className: props.className,
        headerClassName: props.headerClassName,
        ellipsis: props.ellipsis
    };

    // 处理排序（只有叶子列才能排序）
    if (props.sortable && childColumns.value.length === 0) {
        if (props.sortMethod) {
            config.sorter = props.sortMethod;
        } else if (props.sortable === "custom") {
            config.sorter = "custom";
        } else {
            config.sorter = true;
        }
    }

    if (props.defaultSort) {
        config.defaultSortOrder = props.defaultSort;
    }

    // 处理默认插槽（单元格自定义渲染）- 只有叶子列才有单元格渲染
    if (slots.default && childColumns.value.length === 0) {
        config._renderCell = (scope: TableCellScope) => {
            return slots.default!(scope);
        };
    }

    // 处理表头插槽
    if (slots.header) {
        config._renderHeader = (scope: TableHeaderScope) => {
            return slots.header!(scope);
        };
    }

    // 如果有子列，添加 children 属性
    if (childColumns.value.length > 0) {
        config.children = [...childColumns.value];
    }

    return config;
};

// 注册列配置到父级（Table 或父 TableColumn）
const registerColumnConfig = () => {
    const config = buildColumnConfig();

    const parentCtx = resolvedParentColumnContext.value;
    if (parentCtx) {
        // 嵌套在父 TableColumn 中，向父列注册
        parentCtx.registerChildColumn(config);
    } else if (tableContext) {
        // 直接在 Table 中，向 Table 注册
        tableContext.registerColumn(config);
    }
};

// 注销列
const unregisterColumn = () => {
    const parentCtx = resolvedParentColumnContext.value;
    if (parentCtx) {
        parentCtx.unregisterChildColumn(uid);
    } else if (tableContext) {
        tableContext.unregisterColumn(uid);
    }
};

onMounted(() => {
    if (!tableContext && !parentColumnContext) {
        console.warn("[VortTableColumn] 必须在 VortTable 组件内使用");
        return;
    }
    // 确保拿到正确的父列上下文（含 HMR/重复模块兜底）
    resolvedParentColumnContext.value = resolveParentColumnContextFallback();
    // 延迟注册，确保子列先注册完成
    nextTick(() => {
        registerColumnConfig();
    });
});

// 监听 props 变化，重新注册列配置
watch(
    () => [
        props.prop,
        props.label,
        props.width,
        props.align,
        props.fixed,
        props.className,
        props.headerClassName,
        props.sortable,
        props.sortMethod,
        props.defaultSort,
        props.ellipsis
    ],
    () => {
        registerColumnConfig();
    },
    { deep: true }
);

onUnmounted(() => {
    unregisterColumn();
});
</script>

<template>
    <span ref="slotContainerRef" v-show="false" :data-vort-column-uid="uid" style="display: none">
        <!-- 默认插槽：可能是单元格内容，也可能是嵌套的子 TableColumn -->
        <slot :value="undefined" :row="{} as T" :index="0" :column="{} as TableColumn<T>" />
        <slot name="header" :column="{} as TableColumn<T>" />
    </span>
</template>

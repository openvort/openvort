<script setup lang="ts">
import { inject, computed } from "vue";
import { TABLE_ACTIONS_KEY } from "./types";

defineOptions({ name: "TableActionsItem" });

/**
 * TableActionsItem - 表格操作项组件
 *
 * 用于定义单个操作按钮/链接，支持主区域和"更多"下拉菜单两种场景
 * 必须在 TableActions 组件内使用
 *
 * @example
 * ```vue
 * <!-- 主区域操作项 -->
 * <TableActionsItem @click="handleEdit">编辑</TableActionsItem>
 * <TableActionsItem danger @click="handleDelete">删除</TableActionsItem>
 *
 * <!-- 更多下拉菜单中的操作项（使用 in-more 属性） -->
 * <template #more>
 *   <TableActionsItem in-more @click="handleCopy">复制</TableActionsItem>
 *   <TableActionsItem in-more danger @click="handleDelete">删除</TableActionsItem>
 * </template>
 * ```
 */

interface Props {
    /** 是否为危险操作（红色文字） */
    danger?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否在 more 下拉菜单中使用（渲染为 DropdownMenuItem） */
    inMore?: boolean;
    /** 菜单图标（仅 inMore=true 时生效） */
    icon?: string;
}

const props = withDefaults(defineProps<Props>(), {
    danger: false,
    disabled: false,
    inMore: false,
    icon: undefined
});

const emit = defineEmits<{
    click: [event: Event];
}>();

// 从父组件注入上下文
const context = inject(TABLE_ACTIONS_KEY);

if (!context) {
    console.warn("[TableActionsItem] 必须在 TableActions 组件内使用");
}

// 样式类型
const actionType = computed(() => context?.type ?? "text");

// 是否显示分隔线
const showDivider = computed(() => context?.divider ?? true);

// 处理点击事件
const handleClick = (event: Event) => {
    if (props.disabled) {
        if ("preventDefault" in event && typeof event.preventDefault === "function") {
            event.preventDefault();
        }
        if ("stopPropagation" in event && typeof event.stopPropagation === "function") {
            event.stopPropagation();
        }
        return;
    }
    emit("click", event);
};
</script>

<template>
    <!-- more 下拉菜单项（基于 vort-dropdown-menu-item） -->
    <vort-dropdown-menu-item v-if="inMore" :danger="danger" :disabled="disabled" :icon="icon" @click="handleClick">
        <slot />
    </vort-dropdown-menu-item>

    <!-- 主区域操作项（链接/按钮） -->
    <span v-else class="table-actions-item-wrapper" :class="{ 'with-divider': showDivider }">
        <!-- 按钮样式 -->
        <vort-button
            v-if="actionType === 'button'"
            type="text"
            size="small"
            :class="['table-actions-item', danger && 'table-actions-item--danger', disabled && 'table-actions-item--disabled']"
            :disabled="disabled"
            @click="handleClick"
        >
            <slot />
        </vort-button>
        <!-- 文本链接样式 -->
        <a
            v-else
            :class="['table-actions-item', 'table-actions-item--text', danger && 'table-actions-item--danger', disabled && 'table-actions-item--disabled']"
            @click="handleClick"
        >
            <slot />
        </a>
    </span>
</template>

<style scoped>
.table-actions-item-wrapper {
    display: inline-flex;
    align-items: center;
}

/* 带分隔线时，在元素前添加分隔线样式 */
.table-actions-item-wrapper.with-divider::before {
    content: "";
    display: inline-block;
    width: 1px;
    height: 1em;
    background-color: #dcdfe6;
    margin: 0 8px;
    vertical-align: middle;
}

.table-actions-item {
    white-space: nowrap;
    cursor: pointer;
}

.table-actions-item--text {
    color: var(--vort-primary);
    font-size: 14px;
    transition: color 0.2s;
}

.table-actions-item--text:hover {
    color: var(--vort-primary-hover);
}

.table-actions-item--danger {
    color: var(--vort-error) !important;
}

.table-actions-item--danger:hover {
    color: var(--vort-error-hover) !important;
}

.table-actions-item--disabled {
    color: rgba(0, 0, 0, 0.25) !important;
    cursor: not-allowed;
    pointer-events: none;
}
</style>

<script setup lang="ts">
/**
 * TableActionsMoreItem - 表格操作更多菜单项组件
 *
 * 用于 TableActions 的 more 插槽中，定义下拉菜单的操作项
 * 基于 vort-dropdown-menu-item 封装，提供统一的样式和交互
 *
 * @example
 * ```vue
 * <TableActions>
 *   <TableActionsItem @click="handleEdit">编辑</TableActionsItem>
 *   <template #more>
 *     <TableActionsMoreItem @click="handleCopy">复制</TableActionsMoreItem>
 *     <TableActionsMoreItem danger @click="handleDelete">删除</TableActionsMoreItem>
 *   </template>
 * </TableActions>
 *
 * <!-- 配合 DeleteRecord 等业务组件使用 -->
 * <template #more>
 *   <TableActionsMoreItem>
 *     <DeleteRecord :params="{ id: row.id }" :requestApi="api.del">删除</DeleteRecord>
 *   </TableActionsMoreItem>
 * </template>
 * ```
 */

defineOptions({ name: "TableActionsMoreItem" });

interface Props {
    /** 是否为危险操作（红色文字） */
    danger?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 菜单图标 */
    icon?: string;
}

const props = withDefaults(defineProps<Props>(), {
    danger: false,
    disabled: false,
    icon: undefined
});

const emit = defineEmits<{
    click: [event: Event];
}>();

const handleClick = (event: Event) => {
    if (!props.disabled) {
        emit("click", event);
    }
};
</script>

<template>
    <vort-dropdown-menu-item :danger="danger" :disabled="disabled" :icon="icon" @click="handleClick">
        <slot />
    </vort-dropdown-menu-item>
</template>

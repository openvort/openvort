<script setup lang="ts">
import { provide, reactive, useSlots, computed } from "vue";
import { TABLE_ACTIONS_KEY, type TableActionsType, type TableActionsContext } from "./types";

defineOptions({ name: "TableActions" });

/**
 * TableActions - 表格操作栏组件
 *
 * 用于表格操作列的按钮/链接集合
 * 支持：
 * - 显示分隔线（divider）
 * - text/button 两种样式（type）
 * - 超出内容折叠到"更多"下拉菜单（more 插槽）
 *
 * @example
 * ```vue
 * <!-- 基础用法 -->
 * <TableActions>
 *   <TableActionsItem @click="handleEdit">编辑</TableActionsItem>
 *   <TableActionsItem @click="handleView">详情</TableActionsItem>
 *   <TableActionsItem danger @click="handleDelete">删除</TableActionsItem>
 * </TableActions>
 *
 * <!-- 配合 DialogForm 使用 -->
 * <TableActions>
 *   <DialogForm :component="EditForm" title="编辑">
 *     <TableActionsItem>编辑</TableActionsItem>
 *   </DialogForm>
 *   <TableActionsItem danger @click="handleDelete">删除</TableActionsItem>
 * </TableActions>
 *
 * <!-- 带更多下拉菜单 -->
 * <TableActions>
 *   <TableActionsItem @click="handleEdit">编辑</TableActionsItem>
 *   <template #more>
 *     <vort-dropdown-menu-item @click="handleCopy">复制</vort-dropdown-menu-item>
 *     <vort-dropdown-menu-item danger @click="handleDelete">删除</vort-dropdown-menu-item>
 *   </template>
 * </TableActions>
 *
 * <!-- 按钮样式，不带分隔线 -->
 * <TableActions type="button" :divider="false">
 *   <TableActionsItem @click="handleEdit">编辑</TableActionsItem>
 *   <TableActionsItem danger @click="handleDelete">删除</TableActionsItem>
 * </TableActions>
 * ```
 */

interface Props {
    /** 样式类型：text-链接样式（默认），button-按钮样式 */
    type?: TableActionsType;
    /** 是否显示分隔线，默认 true */
    divider?: boolean;
    /** 更多按钮的文字，默认"更多" */
    moreText?: string;
    /**
     * 更多下拉菜单关闭时是否销毁内容（默认：true，保持当前行为）
     *
     * 当 more 插槽内包含 DialogForm 等 Teleport 组件时，可设置为 false，避免 dropdown 关闭导致弹窗组件被卸载。
     */
    moreDestroyOnHidden?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    type: "text",
    divider: true,
    moreText: "更多",
    moreDestroyOnHidden: false
});

// 获取插槽
const slots = useSlots();

// 是否有 more 插槽（计算属性确保响应性）
const hasMoreSlot = computed(() => !!slots.more);

// 提供上下文给子组件
provide(
    TABLE_ACTIONS_KEY,
    reactive<TableActionsContext>({
        type: props.type,
        divider: props.divider
    })
);
</script>

<template>
    <div class="table-actions">
        <!-- 主区域操作项 -->
        <slot />
        <!-- 更多下拉菜单 -->
        <span v-if="hasMoreSlot" class="table-actions-more-wrapper" :class="{ 'with-divider': divider }">
            <vort-dropdown trigger="click" placement="bottomLeft" :destroy-on-hidden="props.moreDestroyOnHidden">
                <!-- 触发器 - 链接样式 -->
                <a v-if="type === 'text'" class="table-actions-more">
                    {{ moreText }}
                    <svg class="table-actions-more-icon" viewBox="0 0 1024 1024" width="12" height="12" fill="currentColor">
                        <path
                            d="M512 714.666667a42.666667 42.666667 0 0 1-30.165333-12.501334l-256-256a42.666667 42.666667 0 0 1 60.330666-60.330666L512 611.669333l225.834667-225.834666a42.666667 42.666667 0 0 1 60.330666 60.330666l-256 256A42.666667 42.666667 0 0 1 512 714.666667z"
                        />
                    </svg>
                </a>
                <!-- 触发器 - 按钮样式 -->
                <vort-button v-else type="text" size="small" class="table-actions-more-btn">
                    {{ moreText }}
                    <svg class="table-actions-more-icon" viewBox="0 0 1024 1024" width="12" height="12" fill="currentColor">
                        <path
                            d="M512 714.666667a42.666667 42.666667 0 0 1-30.165333-12.501334l-256-256a42.666667 42.666667 0 0 1 60.330666-60.330666L512 611.669333l225.834667-225.834666a42.666667 42.666667 0 0 1 60.330666 60.330666l-256 256A42.666667 42.666667 0 0 1 512 714.666667z"
                        />
                    </svg>
                </vort-button>

                <!-- 下拉菜单内容 -->
                <template #overlay>
                    <slot name="more" />
                </template>
            </vort-dropdown>
        </span>
    </div>
</template>

<style scoped>
.table-actions {
    display: inline-flex;
    align-items: center;
    flex-wrap: nowrap;
}

/* 隐藏第一个可见的 table-actions-item-wrapper 的分隔线 */
.table-actions :deep(.table-actions-item-wrapper.with-divider:first-of-type::before),
.table-actions > :first-child :deep(.table-actions-item-wrapper.with-divider::before) {
    display: none;
}

.table-actions-more-wrapper {
    display: inline-flex;
    align-items: center;
}

/* 更多按钮的分隔线 */
.table-actions-more-wrapper.with-divider::before {
    content: "";
    display: inline-block;
    width: 1px;
    height: 1em;
    background-color: #dcdfe6;
    margin: 0 8px;
    vertical-align: middle;
}

/* 如果 more 是唯一的子元素或第一个子元素，隐藏分隔线 */
.table-actions > .table-actions-more-wrapper:first-child::before {
    display: none;
}

.table-actions-more {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    color: var(--vort-primary);
    font-size: 14px;
    cursor: pointer;
    white-space: nowrap;
    transition: color 0.2s;
}

.table-actions-more:hover {
    color: var(--vort-primary-hover);
}

.table-actions-more-btn {
    display: inline-flex;
    align-items: center;
    gap: 2px;
}

.table-actions-more-icon {
    transition: transform 0.2s;
}
</style>

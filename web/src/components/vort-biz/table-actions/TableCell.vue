<script setup lang="ts">
/**
 * TableCell - 表格单元格容器组件
 *
 * 作为表格 td 内的统一容器：
 * - 撑满整个单元格区域
 * - 提供统一的 padding
 * - 可选的 hover 效果
 * - 可选的点击处理
 *
 * @example
 * ```vue
 * <ProTable>
 *   <template #cell="{ record }">
 *     <TableCell @click="handleClick">
 *       <div>内容</div>
 *     </TableCell>
 *   </template>
 * </ProTable>
 * ```
 */

defineOptions({ name: "TableCell" });

const props = withDefaults(defineProps<{
    readonly?: boolean;
}>(), {
    readonly: false,
});

const emit = defineEmits<{
    click: [event: Event];
}>();

const handleClick = (event: Event) => {
    if (!props.readonly) {
        emit("click", event);
    }
};
</script>

<template>
    <div class="table-cell" :class="{ readonly }" @click="handleClick">
        <slot />
    </div>
</template>

<style scoped>
.table-cell {
    width: 100%;
    height: 100%;
    min-height: 48px;
    display: flex;
    align-items: center;
    padding: 8px;
    box-sizing: border-box;
    cursor: pointer;
    position: relative;
}

.table-cell::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border: 1px solid transparent;
    pointer-events: none;
    transition: border-color 0.2s ease;
    z-index: 1;
}

.table-cell:not(.readonly):hover::after {
    border-color: #d9d9d9;
}

.table-cell.readonly {
    cursor: default;
}
</style>

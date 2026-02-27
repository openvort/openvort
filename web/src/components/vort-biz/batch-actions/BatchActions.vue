<script lang="ts" setup>
defineOptions({ name: "BatchActions" });

const props = withDefaults(
    defineProps<{
        selectedCount?: number;
        deleteText?: string;
        confirmText?: string;
    }>(),
    {
        selectedCount: 0,
        deleteText: "批量删除",
        confirmText: "您确认要批量删除所选数据吗？"
    }
);

const emit = defineEmits<{
    delete: [];
}>();
</script>

<template>
    <div class="batch-actions">
        <vort-popconfirm :title="confirmText" @confirm="emit('delete')">
            <vort-button :disabled="props.selectedCount <= 0">
                {{ deleteText }}
            </vort-button>
        </vort-popconfirm>
        <div v-if="props.selectedCount > 0" class="ml-2">
            已选择：<b>{{ props.selectedCount }}</b> 项
        </div>
    </div>
</template>

<style lang="less" scoped>
.batch-actions {
    display: inline-flex;
    align-items: center;
}
</style>

<script setup lang="ts">
import { ref } from "vue";
import { Dropdown, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuSub } from "@openvort/vort-ui";
import { MoreHorizontal, Upload, FileText, Download, Layers, Zap } from "lucide-vue-next";

const emit = defineEmits<{
    import: [];
    importRecords: [];
    exportCsv: [];
    exportExcel: [];
    exportJson: [];
    batchOps: [];
}>();

const open = ref(false);
</script>

<template>
    <Dropdown v-model:open="open" trigger="click" placement="bottomRight">
        <button type="button" class="more-actions-btn">
            <MoreHorizontal :size="18" />
        </button>
        <template #overlay>
            <DropdownMenuItem @click="emit('import')">
                <Upload :size="14" class="mr-2 text-gray-400" />
                <span>导入</span>
            </DropdownMenuItem>
            <DropdownMenuItem @click="emit('importRecords')">
                <FileText :size="14" class="mr-2 text-gray-400" />
                <span>导入记录</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuSub title="导出">
                <template #icon><Download :size="14" class="mr-2 text-gray-400" /></template>
                <DropdownMenuItem @click="emit('exportCsv')">数据报告 (CSV)</DropdownMenuItem>
                <DropdownMenuItem @click="emit('exportExcel')">数据报告 (Excel)</DropdownMenuItem>
                <DropdownMenuItem @click="emit('exportJson')">数据备份 (JSON)</DropdownMenuItem>
            </DropdownMenuSub>
        </template>
    </Dropdown>
</template>

<style scoped>
.more-actions-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    cursor: pointer;
    color: #666;
    transition: all 0.2s;
}
.more-actions-btn:hover {
    border-color: var(--vort-primary, #1456f0);
    color: var(--vort-primary, #1456f0);
    background: var(--vort-primary-bg, rgba(20, 86, 240, 0.04));
}
</style>

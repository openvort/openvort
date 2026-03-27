<script setup lang="ts">
import { ref } from "vue";
import { Dialog, Button } from "@openvort/vort-ui";

const open = defineModel<boolean>("open", { default: false });

const records = ref([
    { operator: "Mansy-1", time: "2025-06-30 11:09:02", file: "缺陷导入2222.xlsx", status: "成功" },
    { operator: "Mansy-1", time: "2025-06-30 09:53:12", file: "缺陷导入APP改版.xlsx", status: "成功" },
    { operator: "Mansy-1", time: "2025-06-30 09:25:18", file: "缺陷导出.xlsx", status: "成功" },
]);
</script>

<template>
    <Dialog v-model:open="open" title="工作项导入记录" width="640px">
        <table class="record-table">
            <thead>
                <tr>
                    <th>操作者</th>
                    <th>导入时间</th>
                    <th>导入文件</th>
                    <th>导入进度</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="(r, i) in records" :key="i">
                    <td>{{ r.operator }}</td>
                    <td>{{ r.time }}</td>
                    <td><a href="#" class="file-link">{{ r.file }}</a></td>
                    <td><span class="status-success">{{ r.status }}</span></td>
                </tr>
                <tr v-if="!records.length">
                    <td colspan="4" class="empty-cell">暂无导入记录</td>
                </tr>
            </tbody>
        </table>

        <template #footer>
            <Button @click="open = false">关闭</Button>
        </template>
    </Dialog>
</template>

<style scoped>
.record-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
.record-table th {
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid #f0f0f0;
    color: #999;
    font-weight: 500;
    font-size: 12px;
}
.record-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #f5f5f5;
    color: #333;
}
.file-link {
    color: var(--vort-primary);
    text-decoration: none;
}
.file-link:hover {
    text-decoration: underline;
}
.status-success {
    color: #52c41a;
    font-weight: 500;
}
.empty-cell {
    text-align: center;
    color: #999;
    padding: 32px !important;
}
</style>

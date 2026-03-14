<script setup lang="ts">
import { ref } from "vue";
import { Dialog, Button, Upload } from "@/components/vort";
import { UploadCloud } from "lucide-vue-next";
import { message } from "@/components/vort";

const open = defineModel<boolean>("open", { default: false });
const fileList = ref<any[]>([]);

const handleUpload = () => {
    if (!fileList.value.length) {
        message.warning("请先选择文件");
        return;
    }
    message.info("导入功能开发中");
    open.value = false;
};
</script>

<template>
    <Dialog v-model:open="open" title="工作项导入" width="520px">
        <div class="import-info">
            <p><strong>文件格式：</strong>xlsx、csv、json</p>
            <p><strong>导入数量：</strong>单次导入行数不超过 10000 行</p>
            <p>
                <strong>模板下载：</strong>
                <a href="#" class="template-link">xlsx 模板</a> |
                <a href="#" class="template-link">csv 模板</a> |
                <a href="#" class="template-link">json 模板</a>
            </p>
        </div>

        <Upload
            accept=".xlsx,.csv,.json"
            :file-list="fileList"
            :max-count="1"
            list-type="text"
            :before-upload="() => false"
            @change="(info: any) => fileList = info.fileList"
        >
            <div class="upload-area">
                <UploadCloud :size="32" class="text-gray-300" />
                <span class="upload-text">点击上传文件</span>
            </div>
        </Upload>

        <template #footer>
            <div class="flex justify-end gap-2">
                <Button @click="open = false">取消</Button>
                <Button type="primary" :disabled="!fileList.length" @click="handleUpload">导入</Button>
            </div>
        </template>
    </Dialog>
</template>

<style scoped>
.import-info {
    margin-bottom: 16px;
    font-size: 13px;
    line-height: 1.8;
    color: #333;
}
.template-link {
    color: #4096ff;
    text-decoration: none;
}
.template-link:hover {
    text-decoration: underline;
}
.upload-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border: 1px dashed #d9d9d9;
    border-radius: 8px;
    padding: 32px;
    cursor: pointer;
    transition: border-color 0.2s;
}
.upload-area:hover {
    border-color: #4096ff;
}
.upload-text {
    font-size: 13px;
    color: #4096ff;
}
</style>

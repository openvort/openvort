<script setup lang="ts">
import { ref } from "vue";
import { Dialog, Button, message } from "@openvort/vort-ui";
import { UploadCloud, Download } from "lucide-vue-next";
import {
    createVortflowStory, createVortflowTask, createVortflowBug,
} from "@/api";

const props = defineProps<{
    projectId?: string;
}>();

const open = defineModel<boolean>("open", { default: false });

const emit = defineEmits<{
    done: [];
}>();

const fileList = ref<File[]>([]);
const importing = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);

const handleFileSelect = (e: Event) => {
    const input = e.target as HTMLInputElement;
    if (input.files?.length) {
        fileList.value = [input.files[0]];
    }
};

const removeFile = () => {
    fileList.value = [];
    if (fileInputRef.value) fileInputRef.value.value = "";
};

const downloadTemplate = (format: "csv" | "json") => {
    if (format === "csv") {
        const bom = "\uFEFF";
        const headers = "标题,类型,优先级,负责人,标签,描述";
        const example = "示例需求,需求,中,,客户需求,这是一个示例需求描述";
        const content = bom + headers + "\n" + example;
        const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "工作项导入模板.csv";
        a.click();
        URL.revokeObjectURL(url);
    } else {
        const template = [{
            title: "示例需求",
            type: "需求",
            priority: "中",
            owner: "",
            tags: ["客户需求"],
            description: "这是一个示例需求描述",
        }];
        const blob = new Blob([JSON.stringify(template, null, 2)], { type: "application/json;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "工作项导入模板.json";
        a.click();
        URL.revokeObjectURL(url);
    }
    message.success("模板已下载");
};

const priorityMap: Record<string, number> = { "紧急": 1, "高": 2, "中": 3, "低": 4 };

const parseCSV = (text: string): Record<string, string>[] => {
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 2) return [];
    const headers = lines[0].split(",").map(h => h.replace(/^"|"$/g, "").trim());
    return lines.slice(1).map(line => {
        const values: string[] = [];
        let current = "";
        let inQuotes = false;
        for (const char of line) {
            if (char === '"') { inQuotes = !inQuotes; continue; }
            if (char === "," && !inQuotes) { values.push(current.trim()); current = ""; continue; }
            current += char;
        }
        values.push(current.trim());
        const obj: Record<string, string> = {};
        headers.forEach((h, i) => { obj[h] = values[i] || ""; });
        return obj;
    });
};

const createItem = async (item: Record<string, any>) => {
    const type = item.type || item["类型"] || "需求";
    const title = item.title || item["标题"] || "";
    if (!title) return;
    const priority = priorityMap[item.priority || item["优先级"] || "中"] || 3;
    const tags = typeof item.tags === "string"
        ? item.tags.split(";").filter(Boolean)
        : Array.isArray(item.tags) ? item.tags : (item["标签"] || "").split(";").filter(Boolean);
    const desc = item.description || item["描述"] || "";

    const base = { title, priority, tags, description: desc, project_id: props.projectId || undefined };
    if (type === "需求") await createVortflowStory(base);
    else if (type === "任务") await createVortflowTask({ ...base, task_type: "fullstack" });
    else if (type === "缺陷") await createVortflowBug({ ...base, severity: 3 });
    else await createVortflowStory(base);
};

const handleUpload = async () => {
    if (!fileList.value.length) {
        message.warning("请先选择文件");
        return;
    }
    const file = fileList.value[0];
    importing.value = true;
    try {
        const text = await file.text();
        let items: Record<string, any>[] = [];

        if (file.name.endsWith(".json")) {
            items = JSON.parse(text);
            if (!Array.isArray(items)) items = [items];
        } else if (file.name.endsWith(".csv")) {
            items = parseCSV(text);
        } else {
            message.error("不支持的文件格式，请使用 CSV 或 JSON");
            return;
        }

        if (items.length === 0) {
            message.warning("文件中没有有效数据");
            return;
        }
        if (items.length > 10000) {
            message.error("单次导入不超过 10000 行");
            return;
        }

        let success = 0;
        let fail = 0;
        for (const item of items) {
            try {
                await createItem(item);
                success++;
            } catch {
                fail++;
            }
        }
        if (fail > 0) message.warning(`导入完成：成功 ${success} 条，失败 ${fail} 条`);
        else message.success(`成功导入 ${success} 条工作项`);
        emit("done");
        open.value = false;
        removeFile();
    } catch (e: any) {
        message.error("文件解析失败：" + (e?.message || "未知错误"));
    } finally {
        importing.value = false;
    }
};
</script>

<template>
    <Dialog v-model:open="open" title="工作项导入" width="520px">
        <div class="import-info">
            <p><strong>文件格式：</strong>csv、json</p>
            <p><strong>导入数量：</strong>单次导入行数不超过 10000 行</p>
            <p>
                <strong>模板下载：</strong>
                <a class="template-link" @click.prevent="downloadTemplate('csv')">
                    <Download :size="12" class="inline" /> csv 模板
                </a>
                <span class="mx-1">|</span>
                <a class="template-link" @click.prevent="downloadTemplate('json')">
                    <Download :size="12" class="inline" /> json 模板
                </a>
            </p>
        </div>

        <div class="upload-area" @click="fileInputRef?.click()">
            <input
                ref="fileInputRef"
                type="file"
                accept=".csv,.json"
                class="hidden"
                @change="handleFileSelect"
            />
            <template v-if="!fileList.length">
                <UploadCloud :size="32" class="text-gray-300" />
                <span class="upload-text">点击选择文件</span>
                <span class="text-xs text-gray-400">支持 csv、json 格式</span>
            </template>
            <template v-else>
                <div class="flex items-center gap-2">
                    <span class="text-sm text-gray-700">{{ fileList[0].name }}</span>
                    <a class="text-xs text-red-500 cursor-pointer" @click.stop="removeFile">移除</a>
                </div>
            </template>
        </div>

        <template #footer>
            <div class="flex justify-end gap-2">
                <Button @click="open = false">取消</Button>
                <Button type="primary" :disabled="!fileList.length" :loading="importing" @click="handleUpload">导入</Button>
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
    color: var(--vort-primary);
    text-decoration: none;
    cursor: pointer;
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
    border-color: var(--vort-primary);
}
.upload-text {
    font-size: 13px;
    color: var(--vort-primary);
}
</style>

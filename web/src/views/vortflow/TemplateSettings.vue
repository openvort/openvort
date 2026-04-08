<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getVortflowDescriptionTemplates, updateVortflowDescriptionTemplate } from "@/api";
import { message } from "@openvort/vort-ui";

type WorkItemType = "需求" | "任务" | "缺陷";

const TYPES: { key: WorkItemType; label: string }[] = [
    { key: "需求", label: "需求" },
    { key: "任务", label: "任务" },
    { key: "缺陷", label: "缺陷" },
];

const PLACEHOLDERS: Record<WorkItemType, string> = {
    "需求": "### 需求背景\n\n### 用户故事\n\n### 验收标准",
    "任务": "### 任务目标\n\n### 实现方案\n\n### 验收标准",
    "缺陷": "### 问题描述\n\n### 重现步骤\n\n### 期望效果\n\n### 实际效果",
};

const activeType = ref<WorkItemType>("需求");
const templates = ref<Record<WorkItemType, string>>({ "需求": "", "任务": "", "缺陷": "" });
const loading = ref(false);
const saving = ref(false);

const loadTemplates = async () => {
    loading.value = true;
    try {
        const res: any = await getVortflowDescriptionTemplates();
        if (res?.items) {
            for (const t of TYPES) {
                templates.value[t.key] = res.items[t.key] ?? "";
            }
        }
    } catch {
        message.error("加载模板失败");
    } finally {
        loading.value = false;
    }
};

const handleSave = async () => {
    saving.value = true;
    try {
        await updateVortflowDescriptionTemplate(activeType.value, {
            content: templates.value[activeType.value],
        });
        message.success("模板已保存");
    } catch {
        message.error("保存失败");
    } finally {
        saving.value = false;
    }
};

const handleCancel = () => {
    loadTemplates();
};

onMounted(loadTemplates);
</script>

<template>
    <div>
        <vort-alert
            type="info"
            class="mb-4"
            message="使用内容模板后，企业成员在新建当前类型的工作项时，将自动填充模板内容，规范企业成员的描述格式。"
        />

        <vort-tabs v-model:active-key="activeType" type="card" :hide-content="true" class="mb-4">
            <vort-tab-pane v-for="t in TYPES" :key="t.key" :tab-key="t.key" :tab="t.label" />
        </vort-tabs>

        <vort-spin :spinning="loading">
            <div class="border border-gray-200 rounded-lg">
                <div class="p-3 border-b border-gray-100 bg-gray-50 rounded-t-lg">
                    <span class="text-xs text-gray-500">示例</span>
                </div>
                <div class="p-1">
                    <textarea
                        v-model="templates[activeType]"
                        class="w-full min-h-[240px] p-3 text-sm text-gray-700 bg-white border-0 outline-none resize-y font-mono leading-relaxed"
                        :placeholder="PLACEHOLDERS[activeType]"
                    />
                </div>
            </div>

            <div class="flex items-center gap-3 mt-4">
                <vort-button variant="primary" :loading="saving" @click="handleSave">保存</vort-button>
                <vort-button @click="handleCancel">取消</vort-button>
            </div>
        </vort-spin>
    </div>
</template>

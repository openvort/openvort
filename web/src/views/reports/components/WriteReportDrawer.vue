<script setup lang="ts">
import { ref, watch } from "vue";
import { z } from "zod";
import { message } from "@openvort/vort-ui";
import { submitReport, getMyPublications } from "@/api";
import { VortEditor } from "@/components/vort-biz/editor";

interface PubItem { id: string; name: string; description: string; report_type: string; content_template?: string; }

const props = defineProps<{
    open: boolean;
    preselectedPub?: PubItem | null;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const step = ref<"select" | "write">("select");
const publications = ref<PubItem[]>([]);
const loadingPubs = ref(false);
const selectedPub = ref<PubItem | null>(null);
const formRef = ref();
const submitting = ref(false);

const form = ref({
    content: "",
    report_date: "",
});

const rules = z.object({
    content: z.string().min(1, "请填写汇报内容"),
});

watch(() => props.open, async (val) => {
    if (val) {
        submitting.value = false;
        form.value = { content: "", report_date: "" };
        if (props.preselectedPub) {
            selectedPub.value = props.preselectedPub;
            if (props.preselectedPub.content_template) {
                form.value.content = props.preselectedPub.content_template;
            }
            step.value = "write";
        } else {
            selectedPub.value = null;
            step.value = "select";
            await loadPublications();
        }
    }
});

async function loadPublications() {
    loadingPubs.value = true;
    try {
        const res: any = await getMyPublications();
        publications.value = res?.publications || [];
    } catch { publications.value = []; }
    finally { loadingPubs.value = false; }
}

function selectTemplate(pub: PubItem) {
    selectedPub.value = pub;
    if (pub.content_template) {
        form.value.content = pub.content_template;
    }
    step.value = "write";
}

function handleClose() {
    emit("update:open", false);
}

async function handleSubmit() {
    try { await formRef.value?.validate(); } catch { return; }
    submitting.value = true;
    try {
        const payload = {
            report_type: selectedPub.value?.report_type || "daily",
            title: `${selectedPub.value?.name || "汇报"} - ${form.value.report_date || new Date().toISOString().slice(0, 10)}`,
            content: form.value.content,
            report_date: form.value.report_date || undefined,
            publication_id: selectedPub.value?.id,
        };
        const res: any = await submitReport(payload);
        if (res?.success) {
            message.success("汇报已提交");
            emit("saved");
            handleClose();
        } else { message.error("提交失败"); }
    } catch { message.error("提交失败"); }
    finally { submitting.value = false; }
}

const typeLabels: Record<string, string> = { daily: "日报", weekly: "周报", monthly: "月报", quarterly: "季报" };
</script>

<template>
    <vort-drawer :open="open" title="写汇报" :width="600" @update:open="handleClose">
        <!-- Step: Select template -->
        <div v-if="step === 'select'">
            <vort-spin :spinning="loadingPubs">
                <div v-if="publications.length" class="space-y-3">
                    <div
                        v-for="pub in publications" :key="pub.id"
                        class="border border-gray-200 rounded-lg p-4 cursor-pointer hover:border-blue-400 hover:bg-blue-50/30 transition-colors"
                        @click="selectTemplate(pub)"
                    >
                        <div class="flex items-center gap-2 mb-1">
                            <span class="text-sm font-medium text-gray-800">{{ pub.name }}</span>
                            <vort-tag size="small" :color="{ daily: 'blue', weekly: 'purple', monthly: 'orange' }[pub.report_type] || 'default'">
                                {{ typeLabels[pub.report_type] || pub.report_type }}
                            </vort-tag>
                        </div>
                        <p class="text-xs text-gray-400 line-clamp-2">{{ pub.description || '暂无描述' }}</p>
                    </div>
                </div>
                <div v-else class="text-gray-400 text-sm text-center py-16">
                    暂无可填写的汇报模板
                </div>
            </vort-spin>
        </div>

        <!-- Step: Write content -->
        <div v-if="step === 'write'">
            <div v-if="selectedPub" class="mb-4 p-3 bg-blue-50 rounded-lg">
                <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-blue-700">{{ selectedPub.name }}</span>
                    <vort-tag size="small" color="blue">{{ typeLabels[selectedPub.report_type] || selectedPub.report_type }}</vort-tag>
                </div>
                <p v-if="selectedPub.description" class="text-xs text-blue-500 mt-1">{{ selectedPub.description }}</p>
            </div>

            <vort-form ref="formRef" :model="form" :rules="rules" label-width="80px">
                <vort-form-item label="日期" name="report_date">
                    <vort-date-picker v-model="form.report_date" value-format="YYYY-MM-DD" placeholder="默认今天" style="width: 100%" />
                </vort-form-item>
                <vort-form-item label="内容" name="content" required>
                    <VortEditor v-model="form.content" placeholder="请输入汇报内容" min-height="300px" />
                </vort-form-item>
            </vort-form>
        </div>

        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="handleClose">取消</vort-button>
                <vort-button v-if="step === 'write' && !preselectedPub" @click="step = 'select'">返回选择</vort-button>
                <vort-button v-if="step === 'write'" variant="primary" :loading="submitting" @click="handleSubmit">提交</vort-button>
            </div>
        </template>
    </vort-drawer>
</template>

<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { getReportDetail, updateReport, withdrawReport } from "@/api";
import { Clock, Pencil, Undo2 } from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import { MarkdownView, VortEditor } from "@/components/vort-biz/editor";
import { useUserStore } from "@/stores";

const props = defineProps<{
    open: boolean;
    reportId: string;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    updated: [];
}>();

interface ReportDetail {
    id: string;
    report_type: string;
    report_date: string;
    title: string;
    content: string;
    status: string;
    reporter_id: string;
    reporter_name: string;
    auto_generated: boolean;
    submitted_at: string | null;
    created_at: string;
    publication_name?: string;
    allow_edit?: boolean;
}

const userStore = useUserStore();
const report = ref<ReportDetail | null>(null);
const loading = ref(false);
const editing = ref(false);
const saving = ref(false);
const editContent = ref("");
const editTitle = ref("");

const typeLabels: Record<string, string> = { daily: "日报", weekly: "周报", monthly: "月报", quarterly: "季报" };
const typeColors: Record<string, string> = { daily: "blue", weekly: "purple", monthly: "orange", quarterly: "cyan" };

const isOwner = computed(() => report.value?.reporter_id === userStore.userInfo.member_id);

const canEdit = computed(() => {
    if (!report.value) return false;
    return isOwner.value && report.value.allow_edit !== false;
});

const canWithdraw = computed(() => {
    if (!report.value) return false;
    return isOwner.value && report.value.status === "submitted";
});

async function loadReport(id: string) {
    editing.value = false;
    loading.value = true;
    try {
        const res: any = await getReportDetail(id);
        report.value = res;
    } catch { report.value = null; }
    finally { loading.value = false; }
}

watch(() => props.open, (val) => {
    if (val && props.reportId) loadReport(props.reportId);
});

watch(() => props.reportId, (id) => {
    if (props.open && id) loadReport(id);
});

function startEdit() {
    if (!report.value) return;
    editTitle.value = report.value.title;
    editContent.value = report.value.content;
    editing.value = true;
}

function cancelEdit() {
    editing.value = false;
}

const withdrawing = ref(false);

async function handleWithdraw() {
    if (!report.value) return;
    withdrawing.value = true;
    try {
        const res: any = await withdrawReport(report.value.id);
        if (res?.success) {
            message.success("已撤回");
            report.value.status = "draft";
            report.value.submitted_at = null;
            emit("updated");
        } else {
            message.error(res?.error || "撤回失败");
        }
    } catch { message.error("撤回失败"); }
    finally { withdrawing.value = false; }
}

async function saveEdit() {
    if (!report.value) return;
    saving.value = true;
    try {
        const res: any = await updateReport(report.value.id, {
            title: editTitle.value,
            content: editContent.value,
        });
        if (res?.success) {
            report.value.title = editTitle.value;
            report.value.content = editContent.value;
            editing.value = false;
            message.success("已保存");
            emit("updated");
        } else {
            message.error(res?.error || "保存失败");
        }
    } catch { message.error("保存失败"); }
    finally { saving.value = false; }
}
</script>

<template>
    <vort-drawer :open="open" title="汇报详情" :width="560" :mask="false" @update:open="emit('update:open', $event)">
        <vort-spin :spinning="loading">
            <template v-if="report">
                <div class="space-y-5">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <vort-tag :color="typeColors[report.report_type] || 'default'">
                                {{ typeLabels[report.report_type] || report.report_type }}
                            </vort-tag>
                            <vort-tag v-if="report.auto_generated" color="cyan">AI 生成</vort-tag>
                        </div>
                        <div class="flex items-center gap-2">
                            <vort-popconfirm v-if="canWithdraw && !editing" title="确认撤回此汇报？撤回后状态将变为草稿。" @confirm="handleWithdraw">
                                <vort-button size="small" :loading="withdrawing">
                                    <Undo2 :size="13" class="mr-1" /> 撤回
                                </vort-button>
                            </vort-popconfirm>
                            <vort-button v-if="canEdit && !editing" size="small" @click="startEdit">
                                <Pencil :size="13" class="mr-1" /> 编辑
                            </vort-button>
                        </div>
                    </div>

                    <div>
                        <h3 class="text-lg font-medium text-gray-800">{{ report.title || '无标题' }}</h3>
                        <div class="flex items-center gap-3 mt-2 text-xs text-gray-400">
                            <span>{{ report.reporter_name }}</span>
                            <span v-if="report.submitted_at" class="flex items-center gap-1">
                                <Clock :size="12" /> {{ report.submitted_at.slice(0, 19).replace('T', ' ') }}
                            </span>
                        </div>
                    </div>

                    <!-- View mode -->
                    <div v-if="!editing" class="bg-gray-50 rounded-lg p-4">
                        <MarkdownView v-if="report.content" :content="report.content" />
                        <span v-else class="text-sm text-gray-400">无内容</span>
                    </div>

                    <!-- Edit mode -->
                    <div v-else class="space-y-3">
                        <div>
                            <label class="block text-xs text-gray-500 mb-1">标题</label>
                            <vort-input v-model="editTitle" placeholder="标题" />
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 mb-1">内容</label>
                            <VortEditor v-model="editContent" min-height="300px" />
                        </div>
                        <div class="flex justify-end gap-2 pt-2">
                            <vort-button size="small" @click="cancelEdit">取消</vort-button>
                            <vort-button size="small" variant="primary" :loading="saving" @click="saveEdit">保存</vort-button>
                        </div>
                    </div>
                </div>
            </template>
            <div v-else-if="!loading" class="text-gray-400 text-sm text-center py-16">汇报不存在</div>
        </vort-spin>
    </vort-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { CheckCircle, XCircle, AlertCircle, SkipForward, Bug } from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import {
    addVortflowTestPlanExecution,
    getVortflowTestPlanExecutions,
} from "@/api";
import { useWorkItemCommon } from "../work-item/useWorkItemCommon";

interface Props {
    open: boolean;
    planId: string;
    planCaseId: string;
    caseTitle?: string;
    modulePath?: string;
    defaultResult?: string;
}

const props = withDefaults(defineProps<Props>(), {
    caseTitle: "",
    modulePath: "",
    defaultResult: "",
});

const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const { getAvatarBg, getAvatarLabel, getMemberAvatarUrl, loadMemberOptions } = useWorkItemCommon();

const RESULT_OPTIONS = [
    { value: "passed", label: "通过", icon: CheckCircle, color: "text-green-500", bg: "bg-green-50", border: "border-green-500" },
    { value: "blocked", label: "受阻", icon: AlertCircle, color: "text-orange-400", bg: "bg-orange-50", border: "border-orange-400" },
    { value: "failed", label: "失败", icon: XCircle, color: "text-red-500", bg: "bg-red-50", border: "border-red-500" },
    { value: "skipped", label: "跳过", icon: SkipForward, color: "text-blue-400", bg: "bg-blue-50", border: "border-blue-400" },
];

const RESULT_CONFIG: Record<string, { icon: any; color: string; label: string }> = {
    passed: { icon: CheckCircle, color: "text-green-500", label: "通过" },
    blocked: { icon: AlertCircle, color: "text-orange-400", label: "受阻" },
    failed: { icon: XCircle, color: "text-red-500", label: "失败" },
    skipped: { icon: SkipForward, color: "text-blue-400", label: "跳过" },
};

const selectedResult = ref<string>("");
const notesDraft = ref<string>("");
const submitting = ref(false);

const executions = ref<any[]>([]);
const executionsLoading = ref(false);

const canSubmit = computed(() => !!selectedResult.value && !submitting.value);

const resetForm = () => {
    selectedResult.value = props.defaultResult || "";
    notesDraft.value = "";
};

const loadExecutions = async () => {
    if (!props.planId || !props.planCaseId) return;
    executionsLoading.value = true;
    try {
        const res = await getVortflowTestPlanExecutions(props.planId, props.planCaseId) as any;
        executions.value = res?.items || [];
    } catch {
        executions.value = [];
    } finally {
        executionsLoading.value = false;
    }
};

const handleSubmit = async () => {
    if (!selectedResult.value) {
        message.warning("请先选择执行结果");
        return;
    }
    submitting.value = true;
    try {
        const res = await addVortflowTestPlanExecution(props.planId, props.planCaseId, {
            result: selectedResult.value,
            notes: notesDraft.value || "",
        }) as any;
        if (res?.error) {
            message.error(res.error);
            return;
        }
        message.success("已记录执行结果");
        notesDraft.value = "";
        selectedResult.value = "";
        await loadExecutions();
        emit("saved");
    } catch {
        message.error("提交失败");
    } finally {
        submitting.value = false;
    }
};

const handleClose = () => {
    emit("update:open", false);
};

const formatTime = (iso?: string) => (iso ? iso.replace("T", " ").slice(0, 19) : "");

watch(() => props.open, async (val) => {
    if (val) {
        resetForm();
        await Promise.all([loadMemberOptions(), loadExecutions()]);
    }
});

watch(() => props.defaultResult, (val) => {
    if (props.open) {
        selectedResult.value = val || "";
    }
});
</script>

<template>
    <vort-drawer :open="open" :width="780" @update:open="handleClose">
        <template #title>
            <div class="exec-drawer-header">
                <div v-if="modulePath" class="exec-drawer-breadcrumb">{{ modulePath }}</div>
                <div class="exec-drawer-title">
                    <span class="exec-drawer-title-label">执行结果 ·</span>
                    <span class="exec-drawer-title-text">{{ caseTitle || "用例" }}</span>
                </div>
            </div>
        </template>

        <div class="exec-drawer-body">
            <!-- Add execution section -->
            <section class="exec-section">
                <h4 class="exec-section-title">新增执行结果</h4>

                <div class="exec-result-picker">
                    <button
                        v-for="opt in RESULT_OPTIONS"
                        :key="opt.value"
                        type="button"
                        class="exec-result-chip"
                        :class="[
                            selectedResult === opt.value ? `${opt.bg} ${opt.border} exec-result-chip-active` : 'border-gray-200',
                        ]"
                        @click="selectedResult = opt.value"
                    >
                        <component :is="opt.icon" :size="16" :class="opt.color" />
                        <span :class="selectedResult === opt.value ? opt.color : 'text-gray-600'">{{ opt.label }}</span>
                    </button>
                </div>

                <div class="exec-editor-wrap">
                    <VortEditor
                        v-model="notesDraft"
                        placeholder="备注（可选）：可粘贴截图、接口响应、Markdown 表格……"
                        min-height="200px"
                    />
                </div>

                <div class="exec-section-footer">
                    <span class="exec-tip">支持 Markdown，Ctrl/⌘+V 粘贴图片将自动上传</span>
                    <div class="flex items-center gap-2">
                        <vort-button :disabled="submitting" @click="handleClose">取消</vort-button>
                        <vort-button variant="primary" :loading="submitting" :disabled="!canSubmit" @click="handleSubmit">
                            提交执行结果
                        </vort-button>
                    </div>
                </div>
            </section>

            <!-- History section -->
            <section class="exec-section">
                <h4 class="exec-section-title">
                    执行历史
                    <span v-if="executions.length" class="exec-history-count">{{ executions.length }}</span>
                </h4>

                <vort-spin :spinning="executionsLoading">
                    <p v-if="!executionsLoading && executions.length === 0" class="exec-empty">暂无执行记录</p>
                    <div v-else class="exec-history-list">
                        <div v-for="ex in executions" :key="ex.id" class="exec-item">
                            <div class="exec-item-header">
                                <div class="exec-item-meta">
                                    <component
                                        v-if="RESULT_CONFIG[ex.result]"
                                        :is="RESULT_CONFIG[ex.result].icon"
                                        :size="14"
                                        :class="RESULT_CONFIG[ex.result].color"
                                    />
                                    <span class="exec-item-result" :class="RESULT_CONFIG[ex.result]?.color || 'text-gray-500'">
                                        {{ RESULT_CONFIG[ex.result]?.label || ex.result }}
                                    </span>
                                    <template v-if="ex.executor_name">
                                        <span class="exec-item-dot">·</span>
                                        <span
                                            class="exec-item-avatar"
                                            :style="{ backgroundColor: getAvatarBg(ex.executor_name) }"
                                        >
                                            <img
                                                v-if="getMemberAvatarUrl(ex.executor_name)"
                                                :src="getMemberAvatarUrl(ex.executor_name)"
                                                class="w-full h-full object-cover"
                                            >
                                            <template v-else>{{ getAvatarLabel(ex.executor_name) }}</template>
                                        </span>
                                        <span class="exec-item-executor">{{ ex.executor_name }}</span>
                                    </template>
                                </div>
                                <div class="exec-item-extra">
                                    <span v-if="ex.bug_id" class="exec-item-bug" title="已关联缺陷">
                                        <Bug :size="12" />
                                        已关联缺陷
                                    </span>
                                    <span class="exec-item-time">{{ formatTime(ex.created_at) }}</span>
                                </div>
                            </div>
                            <div v-if="ex.notes" class="exec-item-notes">
                                <MarkdownView :content="ex.notes" />
                            </div>
                            <div v-else class="exec-item-notes-empty">无备注</div>
                        </div>
                    </div>
                </vort-spin>
            </section>
        </div>
    </vort-drawer>
</template>

<style scoped>
.exec-drawer-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.exec-drawer-breadcrumb {
    font-size: 12px;
    color: var(--vort-text-tertiary);
}

.exec-drawer-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 16px;
    font-weight: 600;
    color: var(--vort-text);
}

.exec-drawer-title-label {
    color: var(--vort-text-tertiary);
    font-weight: 500;
}

.exec-drawer-title-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.exec-drawer-body {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.exec-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.exec-section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 600;
    color: var(--vort-text);
    margin: 0;
}

.exec-history-count {
    font-size: 12px;
    color: var(--vort-primary, #3b82f6);
    font-weight: 500;
}

.exec-result-picker {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.exec-result-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    font-size: 13px;
    background: #fff;
    border: 1px solid;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.15s;
}

.exec-result-chip:hover {
    border-color: var(--vort-primary, #3b82f6);
}

.exec-result-chip-active {
    font-weight: 500;
}

.exec-editor-wrap {
    border-radius: 6px;
}

.exec-section-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 4px;
}

.exec-tip {
    font-size: 12px;
    color: var(--vort-text-tertiary);
}

.exec-empty {
    font-size: 13px;
    color: var(--vort-text-tertiary);
    text-align: center;
    padding: 24px 0;
    margin: 0;
}

.exec-history-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.exec-item {
    border: 1px solid var(--vort-border-secondary, #f0f0f0);
    border-radius: 8px;
    overflow: hidden;
}

.exec-item-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 12px;
    background: var(--vort-bg-secondary, #fafafa);
}

.exec-item-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
}

.exec-item-result {
    font-size: 13px;
    font-weight: 500;
}

.exec-item-dot {
    color: var(--vort-text-tertiary);
    font-size: 12px;
}

.exec-item-avatar {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    color: #fff;
    font-size: 10px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    flex-shrink: 0;
}

.exec-item-executor {
    font-size: 12px;
    color: var(--vort-text-secondary);
}

.exec-item-extra {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
}

.exec-item-bug {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: #ea580c;
}

.exec-item-time {
    font-size: 12px;
    color: var(--vort-text-tertiary);
}

.exec-item-notes {
    padding: 12px 14px;
    font-size: 13px;
    color: var(--vort-text);
    line-height: 1.6;
}

.exec-item-notes :deep(img) {
    max-width: 100%;
    border-radius: 4px;
    border: 1px solid var(--vort-border-secondary, #f0f0f0);
}

.exec-item-notes :deep(pre) {
    background: var(--vort-bg-secondary, #f8fafc);
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 12px;
}

.exec-item-notes :deep(code) {
    background: var(--vort-bg-secondary, #f3f4f6);
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
}

.exec-item-notes :deep(pre code) {
    background: transparent;
    padding: 0;
}

.exec-item-notes-empty {
    padding: 10px 14px;
    font-size: 12px;
    color: var(--vort-text-tertiary);
    font-style: italic;
}
</style>

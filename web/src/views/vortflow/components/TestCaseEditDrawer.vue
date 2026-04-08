<script setup lang="ts">
import { ref, watch, computed, nextTick } from "vue";
import { Plus, Trash2 } from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import {
    getVortflowTestCase, createVortflowTestCase, updateVortflowTestCase,
    getVortflowTestModules,
} from "@/api";
import { useWorkItemCommon } from "../work-item/useWorkItemCommon";

interface Props {
    open: boolean;
    mode: "add" | "edit";
    caseId?: string;
    projectId: string;
    defaultModuleId?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const { memberOptions, loadMemberOptions } = useWorkItemCommon();

interface StepItem {
    order: number;
    description: string;
    expected_result: string;
}

const loading = ref(false);
const title = ref("");
const precondition = ref("");
const notes = ref("");
const caseType = ref("functional");
const priority = ref(2);
const moduleId = ref<string | null>(null);
const maintainerId = ref<string | null>(null);
const steps = ref<StepItem[]>([{ order: 1, description: "", expected_result: "" }]);

const modules = ref<{ id: string; name: string; parent_id: string | null }[]>([]);
const moduleOptions = computed(() => modules.value.map((m) => ({ label: m.name, value: m.id })));

const CASE_TYPE_OPTIONS = [
    { label: "功能测试", value: "functional" },
    { label: "性能测试", value: "performance" },
    { label: "接口测试", value: "api" },
    { label: "UI 测试", value: "ui" },
    { label: "安全测试", value: "security" },
];

const PRIORITY_OPTIONS = [
    { label: "P0", value: 0 },
    { label: "P1", value: 1 },
    { label: "P2", value: 2 },
    { label: "P3", value: 3 },
];

const drawerTitle = computed(() => (props.mode === "add" ? "新建测试用例" : "编辑测试用例"));

const resetForm = () => {
    title.value = "";
    precondition.value = "";
    notes.value = "";
    caseType.value = "functional";
    priority.value = 2;
    moduleId.value = props.defaultModuleId || null;
    maintainerId.value = null;
    steps.value = [{ order: 1, description: "", expected_result: "" }];
};

const loadDetail = async () => {
    if (!props.caseId) return;
    loading.value = true;
    try {
        const res = await getVortflowTestCase(props.caseId) as any;
        if (res?.error) { message.error(res.error); return; }
        title.value = res.title || "";
        precondition.value = res.precondition || "";
        notes.value = res.notes || "";
        caseType.value = res.case_type || "functional";
        priority.value = res.priority ?? 2;
        moduleId.value = res.module_id || null;
        maintainerId.value = res.maintainer_id || null;
        const rawSteps = res.steps || [];
        steps.value = rawSteps.length > 0 ? rawSteps : [{ order: 1, description: "", expected_result: "" }];
    } catch { message.error("加载用例失败"); }
    finally { loading.value = false; resizeAllTextareas(); }
};

const loadModules = async () => {
    if (!props.projectId) return;
    try {
        const res = await getVortflowTestModules({ project_id: props.projectId });
        modules.value = (res as any)?.items || [];
    } catch { modules.value = []; }
};

const addStep = () => {
    steps.value.push({ order: steps.value.length + 1, description: "", expected_result: "" });
};

const removeStep = (index: number) => {
    steps.value.splice(index, 1);
    steps.value.forEach((s, i) => { s.order = i + 1; });
};

const stepsTableRef = ref<HTMLElement | null>(null);

const autoResize = (e: Event) => {
    const el = e.target as HTMLTextAreaElement;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
};

const resizeAllTextareas = () => {
    nextTick(() => {
        stepsTableRef.value?.querySelectorAll<HTMLTextAreaElement>(".tc-step-input").forEach((el) => {
            el.style.height = "auto";
            el.style.height = el.scrollHeight + "px";
        });
    });
};

const handleSubmit = async () => {
    if (!title.value.trim()) { message.warning("请输入用例标题"); return; }
    loading.value = true;
    try {
        const validSteps = steps.value.filter((s) => s.description.trim() || s.expected_result.trim());
        if (props.mode === "add") {
            const res = await createVortflowTestCase({
                project_id: props.projectId,
                module_id: moduleId.value,
                title: title.value.trim(),
                precondition: precondition.value,
                notes: notes.value,
                case_type: caseType.value,
                priority: priority.value,
                maintainer_id: maintainerId.value,
                steps: validSteps,
            });
            if ((res as any)?.error) { message.error((res as any).error); return; }
            message.success("创建成功");
        } else {
            const res = await updateVortflowTestCase(props.caseId!, {
                module_id: moduleId.value,
                title: title.value.trim(),
                precondition: precondition.value,
                notes: notes.value,
                case_type: caseType.value,
                priority: priority.value,
                maintainer_id: maintainerId.value,
                steps: validSteps,
            });
            if ((res as any)?.error) { message.error((res as any).error); return; }
            message.success("更新成功");
        }
        emit("saved");
    } catch { message.error("操作失败"); }
    finally { loading.value = false; }
};

const handleClose = () => { emit("update:open", false); };

watch(() => props.open, (val) => {
    if (val) {
        loadModules();
        loadMemberOptions();
        if (props.mode === "edit" && props.caseId) {
            loadDetail();
        } else {
            resetForm();
        }
    }
});
</script>

<template>
    <vort-drawer :open="open" :title="drawerTitle" :width="720" @update:open="handleClose">
        <vort-spin :spinning="loading">
            <div class="tc-edit-form">
                <div class="tc-edit-main">
                    <vort-form label-width="80px">
                        <vort-form-item label="标题" required>
                            <vort-input v-model="title" placeholder="请输入用例标题" />
                        </vort-form-item>

                        <vort-form-item label="前置条件">
                            <vort-textarea v-model="precondition" placeholder="请输入前置条件" :rows="3" />
                        </vort-form-item>

                        <vort-form-item label="用例步骤">
                            <div ref="stepsTableRef" class="tc-steps-table">
                                <div class="tc-steps-header">
                                    <span class="tc-steps-col-order">顺序</span>
                                    <span class="tc-steps-col-desc">步骤描述</span>
                                    <span class="tc-steps-col-expect">预期结果</span>
                                    <span class="tc-steps-col-action"></span>
                                </div>
                                <div v-for="(step, idx) in steps" :key="idx" class="tc-steps-row">
                                    <span class="tc-steps-col-order">{{ step.order }}</span>
                                    <div class="tc-steps-col-desc">
                                        <textarea v-model="step.description" class="tc-step-input" placeholder="请输入步骤描述" rows="1" @input="autoResize" />
                                    </div>
                                    <div class="tc-steps-col-expect">
                                        <textarea v-model="step.expected_result" class="tc-step-input" placeholder="请输入预期结果" rows="1" @input="autoResize" />
                                    </div>
                                    <div class="tc-steps-col-action">
                                        <button v-if="steps.length > 1" class="tc-step-remove" @click="removeStep(idx)">
                                            <Trash2 :size="14" />
                                        </button>
                                    </div>
                                </div>
                                <button class="tc-step-add" @click="addStep">
                                    <Plus :size="14" /> 添加步骤
                                </button>
                            </div>
                        </vort-form-item>

                        <vort-form-item label="备注">
                            <vort-textarea v-model="notes" placeholder="请输入备注内容" :rows="3" />
                        </vort-form-item>
                    </vort-form>
                </div>

                <div class="tc-edit-sidebar">
                    <div class="tc-edit-field">
                        <label>功能模块</label>
                        <vort-select v-model="moduleId" placeholder="请选择功能模块" allow-clear style="width: 100%">
                            <vort-select-option v-for="opt in moduleOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                        </vort-select>
                    </div>
                    <div class="tc-edit-field">
                        <label>用例类型</label>
                        <vort-select v-model="caseType" style="width: 100%">
                            <vort-select-option v-for="opt in CASE_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                        </vort-select>
                    </div>
                    <div class="tc-edit-field">
                        <label>优先级</label>
                        <vort-select v-model="priority" style="width: 100%">
                            <vort-select-option v-for="opt in PRIORITY_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                        </vort-select>
                    </div>
                    <div class="tc-edit-field">
                        <label>维护人</label>
                        <vort-select v-model="maintainerId" placeholder="请选择维护人" allow-clear style="width: 100%">
                            <vort-select-option v-for="m in memberOptions" :key="m.id" :value="m.id">{{ m.name }}</vort-select-option>
                        </vort-select>
                    </div>
                </div>
            </div>
        </vort-spin>

        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="handleClose">取消</vort-button>
                <vort-button variant="primary" :loading="loading" @click="handleSubmit">保存</vort-button>
            </div>
        </template>
    </vort-drawer>
</template>

<style scoped>
.tc-edit-form {
    display: flex;
    gap: 24px;
}

.tc-edit-main {
    flex: 1;
    min-width: 0;
}

.tc-edit-sidebar {
    width: 200px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-top: 4px;
}

.tc-edit-field label {
    display: block;
    font-size: 13px;
    color: var(--vort-text-secondary);
    margin-bottom: 6px;
}

/* Steps table */
.tc-steps-table {
    border: 1px solid var(--vort-border-secondary, #f0f0f0);
    border-radius: 6px;
    overflow: hidden;
}

.tc-steps-header {
    display: flex;
    align-items: center;
    gap: 0;
    background: var(--vort-bg-secondary, #fafafa);
    font-size: 12px;
    color: var(--vort-text-secondary);
    font-weight: 500;
}

.tc-steps-row {
    display: flex;
    align-items: stretch;
    gap: 0;
    border-top: 1px solid var(--vort-border-secondary, #f0f0f0);
}

.tc-steps-col-order {
    width: 48px;
    flex-shrink: 0;
    text-align: center;
    padding: 8px 4px;
    padding-top: 10px;
    font-size: 13px;
    color: var(--vort-text-tertiary);
}

.tc-steps-col-desc {
    flex: 1;
    min-width: 0;
    padding: 4px;
    border-left: 1px solid var(--vort-border-secondary, #f0f0f0);
}

.tc-steps-col-expect {
    flex: 1;
    min-width: 0;
    padding: 4px;
    border-left: 1px solid var(--vort-border-secondary, #f0f0f0);
}

.tc-steps-col-action {
    width: 36px;
    flex-shrink: 0;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 6px;
}

.tc-step-input {
    width: 100%;
    padding: 4px 8px;
    font-size: 13px;
    color: var(--vort-text);
    border: none;
    outline: none;
    background: transparent;
    resize: none;
    overflow: hidden;
    line-height: 1.5;
    font-family: inherit;
    min-height: 30px;
}

.tc-step-input:focus {
    background: var(--vort-primary-bg, #eff6ff);
}

.tc-step-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    color: var(--vort-text-tertiary);
    background: none;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.tc-step-remove:hover {
    color: #dc2626;
    background: #fee2e2;
}

.tc-step-add {
    display: flex;
    align-items: center;
    gap: 4px;
    width: 100%;
    padding: 8px 12px;
    font-size: 13px;
    color: var(--vort-primary);
    background: none;
    border: none;
    border-top: 1px solid var(--vort-border-secondary, #f0f0f0);
    cursor: pointer;
    transition: background 0.1s;
}

.tc-step-add:hover {
    background: var(--vort-primary-bg);
}
</style>

<script setup lang="ts">
import { ref, watch } from "vue";
import { z } from "zod";
import { Info } from "lucide-vue-next";
import { DownOutlined } from "@/components/vort/icons";
import { useVortFlowStore } from "@/stores";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import { useWorkItemCommon } from "../work-item/useWorkItemCommon";
import { createVortflowIteration, updateVortflowIteration } from "@/api";

export interface IterationFormData {
    id?: string;
    project_id?: string;
    name?: string;
    goal?: string;
    start_date?: string;
    end_date?: string;
    status?: string;
    owner_id?: string;
    assignee_id?: string;
    pm_id?: string;
    estimate_hours?: number | null;
    use_doc_template?: boolean;
}

interface Props {
    open: boolean;
    mode?: "add" | "edit";
    iteration?: IterationFormData;
}

const props = withDefaults(defineProps<Props>(), {
    mode: "add",
    iteration: () => ({}),
});

const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const vortFlowStore = useVortFlowStore();
const {
    ownerGroups, getAvatarBg, getAvatarLabel, getMemberAvatarUrl,
    loadMemberOptions, getMemberIdByName, getMemberNameById,
} = useWorkItemCommon();

const formRef = ref();
const formLoading = ref(false);
const formData = ref<Partial<IterationFormData>>({});
const ownerDropdownOpen = ref(false);
const ownerKeyword = ref("");

const validationSchema = z.object({
    project_id: z.string().min(1, "请选择项目"),
    name: z.string().min(1, "标题必填"),
    owner_id: z.string().optional(),
    goal: z.string().optional(),
    start_date: z.string().optional(),
    end_date: z.string().optional(),
    estimate_hours: z.union([z.number(), z.string(), z.null()]).optional(),
    use_doc_template: z.boolean().optional(),
    status: z.string().optional(),
});

const dialogTitle = ref("");

watch(() => props.open, (val) => {
    if (!val) return;
    loadMemberOptions();
    if (props.mode === "add") {
        dialogTitle.value = "新建迭代";
        formData.value = {
            status: "planning",
            use_doc_template: true,
            owner_id: "",
            project_id: props.iteration?.project_id || vortFlowStore.selectedProjectId || "",
        };
    } else {
        dialogTitle.value = "编辑迭代";
        const i = props.iteration;
        formData.value = {
            ...i,
            owner_id: i.owner_id || i.assignee_id || i.pm_id || "",
            start_date: i.start_date ? i.start_date.split("T")[0] : "",
            end_date: i.end_date ? i.end_date.split("T")[0] : "",
        };
    }
}, { immediate: true });

const handleOwnerSelect = (name: string) => {
    formData.value.owner_id = getMemberIdByName(name);
    ownerDropdownOpen.value = false;
    ownerKeyword.value = "";
};

const handleSave = async (andContinue = false) => {
    try { await formRef.value?.validate(); } catch { return; }
    const r = formData.value;
    const estimateHours = typeof r.estimate_hours === "number" ? r.estimate_hours : undefined;
    formLoading.value = true;
    try {
        if (props.mode === "add") {
            await createVortflowIteration({
                project_id: r.project_id!, name: r.name!,
                goal: r.goal || "", owner_id: r.owner_id || undefined,
                start_date: r.start_date || undefined, end_date: r.end_date || undefined,
                status: r.status || "planning", estimate_hours: estimateHours,
            });
            if (!andContinue) {
                emit("update:open", false);
            } else {
                formData.value = {
                    project_id: r.project_id, status: "planning",
                    use_doc_template: r.use_doc_template ?? true,
                    owner_id: r.owner_id || "", name: "", goal: "",
                    start_date: "", end_date: "", estimate_hours: undefined,
                };
            }
        } else {
            await updateVortflowIteration(r.id!, {
                name: r.name, goal: r.goal,
                owner_id: r.owner_id || undefined,
                start_date: r.start_date || undefined, end_date: r.end_date || undefined,
                status: r.status, estimate_hours: estimateHours,
            });
            emit("update:open", false);
        }
        emit("saved");
    } finally { formLoading.value = false; }
};
</script>

<template>
    <vort-dialog
        :open="open"
        :title="dialogTitle"
        :width="800"
        :centered="true"
        @update:open="emit('update:open', $event)"
    >
        <vort-form ref="formRef" :model="formData" :rules="validationSchema" label-width="90px">
            <vort-form-item v-if="mode === 'add'" label="所属项目" name="project_id" required>
                <vort-select v-model="formData.project_id" placeholder="请选择项目" class="w-full">
                    <vort-select-option v-for="p in vortFlowStore.projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                </vort-select>
            </vort-form-item>

            <div class="grid grid-cols-2 gap-x-4">
                <vort-form-item label="标题" name="name" required>
                    <vort-input v-model="formData.name" placeholder="请输入标题" class="w-full" />
                </vort-form-item>
                <vort-form-item label="负责人" name="owner_id">
                    <WorkItemMemberPicker
                        mode="owner"
                        :owner="getMemberNameById(formData.owner_id || '')"
                        :groups="ownerGroups"
                        :open="ownerDropdownOpen"
                        v-model:keyword="ownerKeyword"
                        :show-unassigned="true"
                        unassigned-value=""
                        unassigned-label="未分配"
                        :dropdown-max-height="420"
                        :get-avatar-bg="getAvatarBg"
                        :get-avatar-label="getAvatarLabel"
                        :get-avatar-url="getMemberAvatarUrl"
                        @update:open="(o) => ownerDropdownOpen = o"
                        @update:owner="handleOwnerSelect"
                    >
                        <template #trigger="{ open: triggerOpen }">
                            <div
                                class="iter-edit-owner-trigger w-full"
                                :class="{ active: triggerOpen }"
                                tabindex="0"
                                @click.stop="ownerDropdownOpen = !ownerDropdownOpen"
                            >
                                <div class="flex items-center w-full gap-2 min-w-0">
                                    <span class="flex-1 min-w-0 text-sm truncate" :class="formData.owner_id ? 'text-[var(--vort-text,rgba(0,0,0,0.88))]' : 'text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))]'">
                                        {{ getMemberNameById(formData.owner_id || "") || "请选择负责人" }}
                                    </span>
                                    <span class="inline-flex items-center text-xs text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))] ml-auto transition-transform" :class="{ 'rotate-180': triggerOpen }">
                                        <DownOutlined />
                                    </span>
                                </div>
                            </div>
                        </template>
                    </WorkItemMemberPicker>
                </vort-form-item>
            </div>

            <div class="grid grid-cols-2 gap-x-4">
                <vort-form-item label="计划时间" name="start_date">
                    <div class="flex items-center gap-1 w-full">
                        <vort-date-picker v-model="formData.start_date" value-format="YYYY-MM-DD" placeholder="开始日期" class="flex-1 min-w-0" />
                        <span class="text-gray-400 text-sm shrink-0">→</span>
                        <vort-date-picker v-model="formData.end_date" value-format="YYYY-MM-DD" placeholder="结束日期" class="flex-1 min-w-0" />
                    </div>
                </vort-form-item>
                <vort-form-item label="工时规模" name="estimate_hours">
                    <div class="flex items-center gap-2 w-full">
                        <vort-input-number v-model="formData.estimate_hours" placeholder="请输入工时规模" :min="0" class="flex-1" />
                        <span class="text-gray-400 text-sm whitespace-nowrap">小时</span>
                    </div>
                </vort-form-item>
            </div>

            <vort-form-item label="迭代目标" name="goal">
                <vort-textarea v-model="formData.goal" placeholder="请输入迭代目标" :rows="4" class="w-full" />
            </vort-form-item>

            <vort-form-item v-if="mode === 'add'" name="use_doc_template">
                <div class="flex items-center gap-1.5">
                    <vort-checkbox v-model:checked="formData.use_doc_template" />
                    <span class="text-sm text-gray-700">使用文档模板</span>
                    <vort-tooltip title="使用预设的文档模板创建迭代">
                        <Info :size="14" class="text-gray-400 cursor-help" />
                    </vort-tooltip>
                </div>
            </vort-form-item>

            <vort-form-item v-if="mode === 'edit'" label="状态" name="status">
                <vort-select v-model="formData.status" class="w-full">
                    <vort-select-option value="planning">待开始</vort-select-option>
                    <vort-select-option value="active">进行中</vort-select-option>
                    <vort-select-option value="completed">已结束</vort-select-option>
                </vort-select>
            </vort-form-item>
        </vort-form>

        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="emit('update:open', false)">取消</vort-button>
                <vort-button v-if="mode === 'add'" @click="handleSave(true)">新建并继续</vort-button>
                <vort-button variant="primary" :loading="formLoading" @click="handleSave()">确定</vort-button>
            </div>
        </template>
    </vort-dialog>
</template>

<style scoped>
.iter-edit-owner-trigger {
    display: flex;
    align-items: center;
    padding: 4px 11px;
    border-radius: 6px;
    border: 1px solid #d9d9d9;
    background: #fff;
    min-height: 32px;
    transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
    outline: none;
    cursor: pointer;
}

.iter-edit-owner-trigger:hover,
.iter-edit-owner-trigger.active {
    border-color: var(--vort-primary, #1456f0);
}

.iter-edit-owner-trigger:focus-within,
.iter-edit-owner-trigger:focus {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}
</style>

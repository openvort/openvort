<script setup lang="ts">
import { ref, watch } from "vue";
import { z } from "zod";
import { Dialog } from "@/components/vort";
import { DownOutlined } from "@/components/vort/icons";
import { useVortFlowStore } from "@/stores";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import { useWorkItemCommon } from "../work-item/useWorkItemCommon";
import {
    createVortflowTestPlan,
    updateVortflowTestPlan,
    getVortflowIterations,
    getVortflowVersions,
} from "@/api";

interface Props {
    open: boolean;
    editData?: {
        id?: string;
        project_id?: string;
        title?: string;
        description?: string;
        owner_id?: string | null;
        iteration_id?: string | null;
        version_id?: string | null;
        start_date?: string | null;
        end_date?: string | null;
    } | null;
}

const props = withDefaults(defineProps<Props>(), { editData: null });

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
const submitting = ref(false);
const form = ref({
    project_id: "",
    title: "",
    description: "",
    owner_id: "",
    iteration_id: "",
    version_id: "",
    start_date: "",
    end_date: "",
});

const rules = z.object({
    project_id: z.string().min(1, "请选择项目"),
    title: z.string().min(1, "请输入计划标题"),
    owner_id: z.string().min(1, "请选择负责人"),
    start_date: z.string().min(1, "请选择计划时间"),
    description: z.string().optional(),
    iteration_id: z.string().optional(),
    version_id: z.string().optional(),
    end_date: z.string().optional(),
});

const ownerDropdownOpen = ref(false);
const ownerKeyword = ref("");

const iterationOptions = ref<{ id: string; name: string }[]>([]);
const versionOptions = ref<{ id: string; name: string }[]>([]);

const isEdit = () => !!props.editData?.id;

async function loadOptions(projectId?: string) {
    const pid = projectId || form.value.project_id;
    if (!pid) {
        iterationOptions.value = [];
        versionOptions.value = [];
        return;
    }
    const [iterRes, verRes] = await Promise.all([
        getVortflowIterations({ project_id: pid, page_size: 100 }),
        getVortflowVersions({ project_id: pid, page_size: 100 }),
    ]);
    iterationOptions.value = ((iterRes as any).items || []).map((i: any) => ({ id: i.id, name: i.name }));
    versionOptions.value = ((verRes as any).items || []).map((v: any) => ({ id: v.id, name: v.name }));
}

function handleProjectChange() {
    form.value.iteration_id = "";
    form.value.version_id = "";
    loadOptions();
}

watch(() => props.open, async (val) => {
    if (!val) return;
    await loadMemberOptions();
    if (props.editData?.id) {
        form.value = {
            project_id: props.editData.project_id || "",
            title: props.editData.title || "",
            description: props.editData.description || "",
            owner_id: props.editData.owner_id || "",
            iteration_id: props.editData.iteration_id || "",
            version_id: props.editData.version_id || "",
            start_date: props.editData.start_date?.split("T")[0] || "",
            end_date: props.editData.end_date?.split("T")[0] || "",
        };
    } else {
        form.value = {
            project_id: vortFlowStore.selectedProjectId || "",
            title: "",
            description: "",
            owner_id: "",
            iteration_id: "",
            version_id: "",
            start_date: "",
            end_date: "",
        };
    }
    await loadOptions();
    submitting.value = false;
});

const handleOwnerSelect = (name: string) => {
    form.value.owner_id = getMemberIdByName(name);
    ownerDropdownOpen.value = false;
    ownerKeyword.value = "";
};

async function handleSubmit() {
    try { await formRef.value?.validate(); } catch { return; }
    submitting.value = true;
    try {
        const payload = {
            title: form.value.title,
            description: form.value.description,
            owner_id: form.value.owner_id || null,
            iteration_id: form.value.iteration_id || null,
            version_id: form.value.version_id || null,
            start_date: form.value.start_date || null,
            end_date: form.value.end_date || null,
        };
        if (isEdit()) {
            await updateVortflowTestPlan(props.editData!.id!, payload);
        } else {
            await createVortflowTestPlan({ ...payload, project_id: form.value.project_id });
        }
        emit("saved");
        emit("update:open", false);
    } finally {
        submitting.value = false;
    }
}
</script>

<template>
    <Dialog
        :open="open"
        :title="isEdit() ? '编辑测试计划' : '新建测试计划'"
        :confirm-loading="submitting"
        :ok-text="isEdit() ? '保存' : '确定'"
        @ok="handleSubmit"
        @update:open="emit('update:open', $event)"
    >
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="80px">
            <vort-form-item v-if="!isEdit()" label="所属项目" name="project_id" required>
                <vort-select v-model="form.project_id" placeholder="请选择项目" @change="handleProjectChange">
                    <vort-select-option v-for="p in vortFlowStore.projects" :key="p.id" :value="p.id">
                        {{ p.name }}
                    </vort-select-option>
                </vort-select>
            </vort-form-item>

            <vort-form-item label="标题" name="title" required>
                <vort-input v-model="form.title" placeholder="请输入计划标题" />
            </vort-form-item>

            <vort-form-item label="负责人" name="owner_id" required>
                <WorkItemMemberPicker
                    mode="owner"
                    :owner="getMemberNameById(form.owner_id)"
                    :groups="ownerGroups"
                    :open="ownerDropdownOpen"
                    v-model:keyword="ownerKeyword"
                    :show-unassigned="false"
                    :dropdown-max-height="420"
                    :get-avatar-bg="getAvatarBg"
                    :get-avatar-label="getAvatarLabel"
                    :get-avatar-url="getMemberAvatarUrl"
                    @update:open="(o) => ownerDropdownOpen = o"
                    @update:owner="handleOwnerSelect"
                >
                    <template #trigger="{ open: triggerOpen }">
                        <div
                            class="tp-owner-trigger w-full"
                            :class="{ active: triggerOpen }"
                            tabindex="0"
                            @click.stop="ownerDropdownOpen = !ownerDropdownOpen"
                        >
                            <div class="flex items-center w-full gap-2 min-w-0">
                                <template v-if="form.owner_id && getMemberNameById(form.owner_id)">
                                    <span
                                        class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center shrink-0 overflow-hidden"
                                        :style="{ backgroundColor: getAvatarBg(getMemberNameById(form.owner_id)) }"
                                    >
                                        <img
                                            v-if="getMemberAvatarUrl(getMemberNameById(form.owner_id))"
                                            :src="getMemberAvatarUrl(getMemberNameById(form.owner_id))"
                                            class="w-full h-full object-cover"
                                        >
                                        <template v-else>{{ getAvatarLabel(getMemberNameById(form.owner_id)) }}</template>
                                    </span>
                                    <span class="flex-1 min-w-0 text-sm truncate text-[var(--vort-text,rgba(0,0,0,0.88))]">
                                        {{ getMemberNameById(form.owner_id) }}
                                    </span>
                                </template>
                                <span v-else class="flex-1 min-w-0 text-sm truncate text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))]">
                                    请选择
                                </span>
                                <span class="inline-flex items-center text-xs text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))] ml-auto transition-transform" :class="{ 'rotate-180': triggerOpen }">
                                    <DownOutlined />
                                </span>
                            </div>
                        </div>
                    </template>
                </WorkItemMemberPicker>
            </vort-form-item>

            <vort-form-item label="描述" name="description">
                <vort-textarea v-model="form.description" placeholder="用简短的语言来描述一下吧" :rows="3" />
            </vort-form-item>

            <vort-form-item label="关联迭代" name="iteration_id">
                <vort-select v-model="form.iteration_id" placeholder="请选择" allow-clear>
                    <vort-select-option v-for="opt in iterationOptions" :key="opt.id" :value="opt.id">
                        {{ opt.name }}
                    </vort-select-option>
                </vort-select>
            </vort-form-item>

            <vort-form-item label="关联版本" name="version_id">
                <vort-select v-model="form.version_id" placeholder="请选择" allow-clear>
                    <vort-select-option v-for="opt in versionOptions" :key="opt.id" :value="opt.id">
                        {{ opt.name }}
                    </vort-select-option>
                </vort-select>
            </vort-form-item>

            <vort-form-item label="计划时间" name="start_date" required>
                <div class="flex items-center gap-2 w-full">
                    <vort-date-picker
                        v-model="form.start_date"
                        value-format="YYYY-MM-DD"
                        placeholder="开始日期"
                        class="flex-1 min-w-0"
                    />
                    <span class="text-gray-400 text-sm shrink-0">~</span>
                    <vort-date-picker
                        v-model="form.end_date"
                        value-format="YYYY-MM-DD"
                        placeholder="结束日期"
                        class="flex-1 min-w-0"
                    />
                </div>
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>

<style scoped>
.tp-owner-trigger {
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

.tp-owner-trigger:hover,
.tp-owner-trigger.active {
    border-color: var(--vort-primary, #1456f0);
}

.tp-owner-trigger:focus-within,
.tp-owner-trigger:focus {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}
</style>

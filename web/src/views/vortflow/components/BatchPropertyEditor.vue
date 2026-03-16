<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { Button, Select, SelectOption, Dialog, Input, Divider, message } from "@/components/vort";
import WorkItemPriority from "@/components/vort-biz/work-item/WorkItemPriority.vue";
import WorkItemStatus from "@/components/vort-biz/work-item/WorkItemStatus.vue";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import WorkItemTagPicker from "@/components/vort-biz/work-item/WorkItemTagPicker.vue";
import { Minus, Plus } from "lucide-vue-next";
import type { RowItem, WorkItemType, StatusOption } from "@/components/vort-biz/work-item/WorkItemTable.types";
import { useWorkItemCommon } from "../work-item/useWorkItemCommon";
import {
    updateVortflowStory, updateVortflowTask, updateVortflowBug,
    getVortflowIterations, getVortflowVersions, getVortflowStories,
    getVortgitRepos,
} from "@/api";
import { useVortFlowStore } from "@/stores";

interface Props {
    selectedRows: RowItem[];
    workItemType?: WorkItemType;
    statusOptions?: StatusOption[];
}

const props = withDefaults(defineProps<Props>(), {
    workItemType: "缺陷",
    statusOptions: () => [],
});

const emit = defineEmits<{
    submit: [changes: PropertyChange[]];
    cancel: [];
    done: [];
}>();

const open = defineModel<boolean>("open", { default: false });

export interface PropertyChange {
    property: string;
    operator: "set" | "clear";
    value: any;
}

const {
    ownerGroups, memberOptions, toBackendPriorityLevel,
    getBackendStatesByDisplayStatus, getMemberIdByName,
} = useWorkItemCommon();

const vortFlowStore = useVortFlowStore();

const submitting = ref(false);

const repoOptions = ref<{ label: string; value: string }[]>([]);
const iterationOptions = ref<{ label: string; value: string }[]>([]);
const versionOptions = ref<{ label: string; value: string }[]>([]);
const storyOptions = ref<{ label: string; value: string }[]>([]);

const loadDynamicOptions = async () => {
    const projectId = vortFlowStore.selectedProjectId || undefined;
    const [repoRes, iterRes, verRes, storyRes] = await Promise.allSettled([
        getVortgitRepos({ project_id: projectId, page_size: 200 }),
        getVortflowIterations({ project_id: projectId, page_size: 200 }),
        getVortflowVersions({ project_id: projectId, page_size: 200 }),
        getVortflowStories({ project_id: projectId, page_size: 200 }),
    ]);
    if (repoRes.status === "fulfilled") {
        const items = (repoRes.value as any)?.items || [];
        repoOptions.value = items.map((r: any) => ({ label: r.name || r.full_name, value: r.id }));
    }
    if (iterRes.status === "fulfilled") {
        const items = (iterRes.value as any)?.items || [];
        iterationOptions.value = items.map((i: any) => ({ label: i.name, value: i.id }));
    }
    if (verRes.status === "fulfilled") {
        const items = (verRes.value as any)?.items || [];
        versionOptions.value = items.map((v: any) => ({ label: v.name, value: v.id }));
    }
    if (storyRes.status === "fulfilled") {
        const items = (storyRes.value as any)?.items || [];
        storyOptions.value = items.map((s: any) => ({ label: s.title, value: s.id }));
    }
};

const allTagOptions = computed(() => {
    const set = new Set<string>();
    for (const row of props.selectedRows) {
        for (const tag of row.tags || []) {
            if (tag) set.add(tag);
        }
    }
    const defaults = ["客户需求", "演示站", "运营需求", "待开会确认", "已发布", "高优先", "稳定性", "UI优化"];
    for (const t of defaults) set.add(t);
    return [...set];
});

watch(open, (v) => {
    if (v) {
        nextId.value = 1;
        changeRows.value = [{ id: 0, property: "priority", operator: "set", value: null }];
        loadDynamicOptions();
    }
});

const PROPERTY_OPTIONS = [
    { label: "优先级", value: "priority" },
    { label: "工作项状态", value: "status" },
    { label: "负责人", value: "owner" },
    { label: "协作者", value: "collaborators" },
    { label: "标签", value: "tags" },
    { label: "计划时间", value: "planTime" },
    { label: "预计工时", value: "estimateHours" },
    { label: "关联仓库", value: "repo" },
    { label: "关联版本", value: "version" },
    { label: "关联迭代", value: "iteration" },
    { label: "实际开始时间", value: "startAt" },
    { label: "实际结束时间", value: "endAt" },
    { label: "父工作项", value: "parentId" },
];

interface ChangeRow {
    id: number;
    property: string;
    operator: "set" | "clear";
    value: any;
}

const nextId = ref(1);
const changeRows = ref<ChangeRow[]>([
    { id: 0, property: "priority", operator: "set", value: null },
]);

const addRow = () => {
    const usedProps = new Set(changeRows.value.map(r => r.property));
    const available = PROPERTY_OPTIONS.find(o => !usedProps.has(o.value));
    if (available) {
        changeRows.value.push({ id: nextId.value++, property: available.value, operator: "set", value: null });
    }
};

const removeRow = (id: number) => {
    if (changeRows.value.length <= 1) return;
    changeRows.value = changeRows.value.filter(r => r.id !== id);
};

const availableProperties = (currentProp: string) => {
    const used = new Set(changeRows.value.map(r => r.property));
    return PROPERTY_OPTIONS.filter(o => o.value === currentProp || !used.has(o.value));
};

const projectGroups = computed(() => {
    const groups: Record<string, { name: string; items: RowItem[] }> = {};
    for (const row of props.selectedRows) {
        const pid = row.projectId || "unknown";
        const pname = row.projectName || pid;
        if (!groups[pid]) groups[pid] = { name: pname, items: [] };
        groups[pid].items.push(row);
    }
    return Object.values(groups);
});

const buildPatch = (change: PropertyChange, row: RowItem): Record<string, any> => {
    const patch: Record<string, any> = {};
    const val = change.operator === "clear" ? null : change.value;
    switch (change.property) {
        case "priority":
            patch.priority = val ? toBackendPriorityLevel(val) : 4;
            break;
        case "status": {
            const states = val ? getBackendStatesByDisplayStatus(val) : [];
            if (states.length > 0) patch.state = states[0];
            break;
        }
        case "owner": {
            const memberId = val ? getMemberIdByName(val) || val : null;
            if (row.type === "需求") patch.pm_id = memberId;
            else patch.assignee_id = memberId;
            break;
        }
        case "collaborators":
            patch.collaborators = val || [];
            break;
        case "tags":
            patch.tags = val || [];
            break;
        case "planTime":
            if (val && Array.isArray(val) && val.length === 2) {
                patch.deadline = val[1] || null;
            } else {
                patch.deadline = null;
            }
            break;
        case "estimateHours":
            patch.estimate_hours = val ? Number(val) : 0;
            break;
        case "startAt":
            patch.start_at = val;
            break;
        case "endAt":
            patch.end_at = val;
            break;
        case "repo":
            patch.repo_id = val;
            break;
        case "parentId":
            patch.parent_id = val;
            break;
        case "version":
        case "iteration":
            break;
    }
    return patch;
};

const handleSubmit = async () => {
    const unsupported = changeRows.value.filter(
        r => (r.property === "version" || r.property === "iteration") && r.operator === "set",
    );
    if (unsupported.length > 0) {
        message.warning("批量设置迭代/版本暂不支持，请在工作项详情中单独操作");
        return;
    }
    const changes: PropertyChange[] = changeRows.value
        .filter(r => r.operator === "clear" || r.value != null)
        .filter(r => r.property !== "version" && r.property !== "iteration")
        .map(r => ({ property: r.property, operator: r.operator, value: r.value }));
    if (changes.length === 0) {
        message.warning("请至少选择一个要修改的属性");
        return;
    }
    submitting.value = true;
    let successCount = 0;
    let failCount = 0;
    try {
        for (const row of props.selectedRows) {
            const id = String(row.backendId || "").trim();
            if (!id) continue;
            const merged: Record<string, any> = {};
            for (const c of changes) Object.assign(merged, buildPatch(c, row));
            try {
                if (row.type === "需求") await updateVortflowStory(id, merged);
                else if (row.type === "任务") await updateVortflowTask(id, merged);
                else if (row.type === "缺陷") await updateVortflowBug(id, merged);
                successCount++;
            } catch { failCount++; }
        }
        if (failCount > 0) message.warning(`成功 ${successCount} 项，失败 ${failCount} 项`);
        else message.success(`已批量修改 ${successCount} 个工作项`);
        emit("submit", changes);
        emit("done");
        open.value = false;
    } finally {
        submitting.value = false;
    }
};

const handleCancel = () => {
    open.value = false;
    emit("cancel");
};
</script>

<template>
    <Dialog v-model:open="open" title="修改属性" width="720px" @cancel="handleCancel">
        <div class="batch-editor">
            <div v-if="projectGroups.length" class="selected-summary">
                <div v-for="group in projectGroups" :key="group.name" class="project-group-tag">
                    <span class="group-name">{{ group.name }}</span>
                    <span class="group-detail">{{ workItemType }} {{ group.items.length }} 个</span>
                </div>
            </div>
            <div v-else class="empty-hint">请先在表格中选中要修改的工作项</div>

            <Divider style="margin: 12px 0" />

            <div class="change-rows">
                <div v-for="row in changeRows" :key="row.id" class="change-row">
                    <Select v-model="row.property" size="small">
                        <SelectOption
                            v-for="opt in availableProperties(row.property)"
                            :key="opt.value"
                            :value="opt.value"
                        >{{ opt.label }}</SelectOption>
                    </Select>

                    <Select v-model="row.operator" size="small">
                        <SelectOption value="set">修改为</SelectOption>
                        <SelectOption value="clear">清空</SelectOption>
                    </Select>

                    <div v-if="row.operator === 'set'" class="value-editor">
                        <WorkItemPriority
                            v-if="row.property === 'priority'"
                            :model-value="row.value || 'medium'"
                            @change="(v) => row.value = v"
                        />
                        <WorkItemStatus
                            v-else-if="row.property === 'status'"
                            :model-value="row.value || ''"
                            :options="statusOptions"
                            @change="(v) => row.value = v"
                        />
                        <WorkItemMemberPicker
                            v-else-if="row.property === 'owner'"
                            mode="owner"
                            :owner="row.value || ''"
                            :groups="ownerGroups"
                            @update:owner="(v) => row.value = v"
                        />
                        <WorkItemMemberPicker
                            v-else-if="row.property === 'collaborators'"
                            mode="collaborators"
                            :collaborators="row.value || []"
                            :groups="ownerGroups"
                            @update:collaborators="(v) => row.value = v"
                        />
                        <WorkItemTagPicker
                            v-else-if="row.property === 'tags'"
                            :model-value="row.value || []"
                            :options="allTagOptions"
                            @change="(v) => row.value = v"
                        />
                        <vort-range-picker
                            v-else-if="row.property === 'planTime'"
                            :model-value="row.value || []"
                            size="small"
                            value-format="YYYY-MM-DD"
                            :placeholder="['开始日期', '结束日期']"
                            allow-clear
                            style="width: 100%"
                            @change="(v: any) => row.value = v"
                        />
                        <vort-date-picker
                            v-else-if="row.property === 'startAt' || row.property === 'endAt'"
                            :model-value="row.value || ''"
                            size="small"
                            value-format="YYYY-MM-DD"
                            placeholder="选择日期"
                            allow-clear
                            style="width: 100%"
                            @change="(v: any) => row.value = v"
                        />
                        <Input
                            v-else-if="row.property === 'estimateHours'"
                            v-model="row.value"
                            size="small"
                            type="number"
                            placeholder="小时数"
                        />
                        <Select
                            v-else-if="row.property === 'repo'"
                            v-model="row.value"
                            size="small"
                            placeholder="请选择仓库"
                            allow-clear
                        >
                            <SelectOption v-for="o in repoOptions" :key="o.value" :value="o.value">{{ o.label }}</SelectOption>
                        </Select>
                        <Select
                            v-else-if="row.property === 'iteration'"
                            v-model="row.value"
                            size="small"
                            placeholder="请选择迭代"
                            allow-clear
                        >
                            <SelectOption v-for="o in iterationOptions" :key="o.value" :value="o.value">{{ o.label }}</SelectOption>
                        </Select>
                        <Select
                            v-else-if="row.property === 'version'"
                            v-model="row.value"
                            size="small"
                            placeholder="请选择版本"
                            allow-clear
                        >
                            <SelectOption v-for="o in versionOptions" :key="o.value" :value="o.value">{{ o.label }}</SelectOption>
                        </Select>
                        <Select
                            v-else-if="row.property === 'parentId'"
                            v-model="row.value"
                            size="small"
                            placeholder="请选择父工作项"
                            allow-clear
                            show-search
                            :filter-option="(input: string, option: any) => (option?.label || '').toLowerCase().includes(input.toLowerCase())"
                        >
                            <SelectOption v-for="o in storyOptions" :key="o.value" :value="o.value" :label="o.label">{{ o.label }}</SelectOption>
                        </Select>
                        <Input v-else v-model="row.value" size="small" placeholder="请输入" />
                    </div>
                    <div v-else class="value-placeholder">将清空该字段</div>

                    <button type="button" class="remove-row-btn" @click="removeRow(row.id)">
                        <Minus :size="14" />
                    </button>
                </div>
            </div>

            <button
                v-if="changeRows.length < PROPERTY_OPTIONS.length"
                type="button"
                class="add-row-btn"
                @click="addRow"
            >
                <Plus :size="14" />
                <span>修改更多属性</span>
            </button>
        </div>

        <template #footer>
            <div class="flex justify-end gap-2">
                <Button @click="handleCancel">取消</Button>
                <Button type="primary" :loading="submitting" @click="handleSubmit">确认修改</Button>
            </div>
        </template>
    </Dialog>
</template>

<style scoped>
.batch-editor {
    max-height: 500px;
    overflow-y: auto;
}
.selected-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.project-group-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: #f5f5f5;
    border-radius: 4px;
    font-size: 13px;
}
.group-name {
    font-weight: 500;
    color: #333;
}
.group-detail {
    color: #888;
    font-size: 12px;
}
.empty-hint {
    text-align: center;
    color: #999;
    font-size: 13px;
    padding: 8px 0;
}
.change-rows {
    display: flex;
    flex-direction: column;
}
.change-row {
    display: grid;
    grid-template-columns: 150px 110px 1fr 32px;
    gap: 8px;
    align-items: center;
    min-height: 44px;
    padding: 6px 0;
    border-bottom: 1px solid var(--vort-border-color, #f0f0f0);
}
.change-row:last-child {
    border-bottom: none;
}
.value-editor {
    min-width: 0;
}
.value-editor :deep(.vort-select),
.value-editor :deep(.vort-input),
.value-editor :deep(.vort-date-picker),
.value-editor :deep(.vort-range-picker) {
    width: 100%;
}
.value-placeholder {
    font-size: 12px;
    color: #999;
    padding: 4px 8px;
}
.remove-row-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: #ff4d4f;
    cursor: pointer;
    transition: background 0.2s;
}
.remove-row-btn:hover {
    background: rgba(255, 77, 79, 0.08);
}
.add-row-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    border: none;
    background: transparent;
    color: #4096ff;
    cursor: pointer;
    font-size: 13px;
    border-radius: 4px;
    margin-top: 8px;
    transition: background 0.2s;
}
.add-row-btn:hover {
    background: rgba(64, 150, 255, 0.08);
}
</style>

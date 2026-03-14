<script setup lang="ts">
import { ref, computed } from "vue";
import { Button, Select, SelectOption, Dialog, Input, Divider } from "@/components/vort";
import WorkItemPriority from "@/components/vort-biz/work-item/WorkItemPriority.vue";
import WorkItemStatus from "@/components/vort-biz/work-item/WorkItemStatus.vue";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import WorkItemTagPicker from "@/components/vort-biz/work-item/WorkItemTagPicker.vue";
import { Minus, Plus } from "lucide-vue-next";
import type { RowItem, WorkItemType, StatusOption } from "@/components/vort-biz/work-item/WorkItemTable.types";
import { useWorkItemCommon } from "../work-item/useWorkItemCommon";

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
}>();

const open = defineModel<boolean>("open", { default: false });

export interface PropertyChange {
    property: string;
    operator: "set" | "clear";
    value: any;
}

const { ownerGroups, memberOptions } = useWorkItemCommon();

const PROPERTY_OPTIONS = [
    { label: "优先级", value: "priority" },
    { label: "工作项状态", value: "status" },
    { label: "负责人", value: "owner" },
    { label: "协作者", value: "collaborators" },
    { label: "标签", value: "tags" },
    { label: "计划时间", value: "planTime" },
    { label: "预计工时", value: "estimateHours" },
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

const handleSubmit = () => {
    const changes: PropertyChange[] = changeRows.value
        .filter(r => r.operator === "clear" || r.value != null)
        .map(r => ({ property: r.property, operator: r.operator, value: r.value }));
    if (changes.length > 0) {
        emit("submit", changes);
    }
    open.value = false;
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
                    <Select v-model="row.property" size="small" class="prop-select">
                        <SelectOption
                            v-for="opt in availableProperties(row.property)"
                            :key="opt.value"
                            :value="opt.value"
                        >{{ opt.label }}</SelectOption>
                    </Select>

                    <Select v-model="row.operator" size="small" class="op-select">
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
                        <WorkItemTagPicker
                            v-else-if="row.property === 'tags'"
                            :model-value="row.value || []"
                            :tag-options="[]"
                            @change="(v) => row.value = v"
                        />
                        <Input
                            v-else-if="row.property === 'estimateHours'"
                            v-model="row.value"
                            size="small"
                            type="number"
                            placeholder="小时数"
                        />
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
                <Button type="primary" @click="handleSubmit">确认修改</Button>
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
    gap: 8px;
}
.change-row {
    display: flex;
    align-items: center;
    gap: 8px;
}
.prop-select {
    width: 130px;
    flex-shrink: 0;
}
.op-select {
    width: 100px;
    flex-shrink: 0;
}
.value-editor {
    flex: 1;
    min-width: 0;
}
.value-placeholder {
    flex: 1;
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
    flex-shrink: 0;
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

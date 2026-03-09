<script setup lang="ts">
import { ref, computed, reactive, onMounted } from "vue";
import { Popover, message } from "@/components/vort";
import { DownOutlined } from "@/components/vort/icons";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import { useWorkItemCommon } from "./useWorkItemCommon";
import type { WorkItemType, Priority, DateRange, NewBugForm } from "@/components/vort-biz/work-item/WorkItemTable.types";

interface Props {
    type?: WorkItemType;
    title?: string;
}

const props = withDefaults(defineProps<Props>(), {
    type: "缺陷",
    title: "新建缺陷"
});

const emit = defineEmits<{
    close: [];
    success: [data: any];
}>();

const {
    priorityOptions,
    priorityLabelMap,
    priorityClassMap,
    getAvatarBg,
    getAvatarLabel,
    getMemberAvatarUrl,
    loadMemberOptions,
    ownerGroups,
} = useWorkItemCommon();

const defaultDescriptionTemplate = [
    "## 问题描述",
    "<!-- 请详细描述发现的问题 -->",
    "",
    "## 复现步骤",
    "1. ",
    "2. ",
    "3. ",
    "",
    "## 预期结果",
    "<!-- 描述期望的行为 -->",
    "",
    "## 实际结果",
    "<!-- 描述实际发生的情况 -->"
].join("\n");

const createInitialBugForm = (): NewBugForm => ({
    title: "",
    owner: "",
    collaborators: [],
    type: props.type,
    planTime: [],
    project: "VortMall",
    iteration: "",
    version: "",
    priority: "" as any,
    tags: [],
    repo: "",
    branch: "",
    startAt: "",
    endAt: "",
    remark: "",
    description: defaultDescriptionTemplate
});

const createBugForm = reactive<NewBugForm>(createInitialBugForm());

const createBugPriorityDropdownOpen = ref(false);
const createAssigneeDropdownOpen = ref(false);
const createAssigneeKeyword = ref("");
const createAssigneeGroupOpen = reactive<Record<string, boolean>>({});
const createTagDropdownOpen = ref(false);
const createTagKeyword = ref("");
const createAttachments = ref<any[]>([]);

const projectOptions = ["VortMall", "VortAdmin", "VortCMS", "OpenVort"];
const iterationOptions = ["Sprint 1", "Sprint 2", "Sprint 3"];
const versionOptions = ["v1.0.0", "v1.1.0", "v1.2.0"];
const repoOptions = ["frontend", "backend", "mobile"];
const branchOptions = ["main", "develop", "feature/xxx"];

const filteredCreateAssigneeGroups = computed(() => {
    const kw = createAssigneeKeyword.value.trim();
    if (!kw) return ownerGroups.value;
    return ownerGroups.value
        .map((g) => ({
            ...g,
            members: g.members.filter((m) => m.includes(kw))
        }))
        .filter((g) => g.members.length > 0);
});

const isCreateOwner = (member: string): boolean => {
    return createBugForm.owner === member;
};

const isCreateCollaborator = (member: string): boolean => {
    return createBugForm.collaborators.includes(member);
};

const toggleCreateAssigneeMenu = () => {
    createAssigneeDropdownOpen.value = !createAssigneeDropdownOpen.value;
    if (!createAssigneeDropdownOpen.value) createAssigneeKeyword.value = "";
};

const toggleCreateAssigneeGroup = (group: string) => {
    createAssigneeGroupOpen[group] = !createAssigneeGroupOpen[group];
};

const setCreateOwner = (member: string) => {
    createBugForm.owner = member || "";
    createBugForm.collaborators = createBugForm.collaborators.filter((x) => x !== member);
};

const toggleCreateCollaborator = (member: string) => {
    if (createBugForm.owner === member) return;
    const list = [...createBugForm.collaborators];
    const idx = list.indexOf(member);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push(member);
    }
    createBugForm.collaborators = list;
};

const selectCreateBugPriority = (value: Priority) => {
    createBugForm.priority = value;
    createBugPriorityDropdownOpen.value = false;
};

const toggleCreateBugPriorityMenu = () => {
    createBugPriorityDropdownOpen.value = !createBugPriorityDropdownOpen.value;
};

const getTagColor = (tag: string): string => {
    const colors = ["#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#06b6d4"];
    let hash = 0;
    for (let i = 0; i < tag.length; i++) hash = (hash * 31 + tag.charCodeAt(i)) >>> 0;
    return colors[hash % colors.length]!;
};

const tagOptions = ["功能", "Bug", "优化", "文档", "前端", "后端", "移动端", "API", "数据库", "安全"];

const filteredTagOptions = computed(() => {
    const kw = createTagKeyword.value.trim();
    if (!kw) return tagOptions;
    return tagOptions.filter((t) => t.includes(kw));
});

const createBugPlanTimeModel = computed<any>({
    get: () => (createBugForm.planTime.length === 2 ? [...createBugForm.planTime] as DateRange : undefined),
    set: (value) => {
        if (Array.isArray(value) && value.length === 2) {
            createBugForm.planTime = [String(value[0] || ""), String(value[1] || "")] as DateRange;
            return;
        }
        createBugForm.planTime = [];
    }
});

const toggleCreateTagMenu = () => {
    createTagDropdownOpen.value = !createTagDropdownOpen.value;
    if (!createTagDropdownOpen.value) createTagKeyword.value = "";
};

const toggleCreateTagOption = (tag: string) => {
    const list = [...createBugForm.tags];
    const idx = list.indexOf(tag);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push(tag);
    }
    createBugForm.tags = list;
};

const resetForm = () => {
    Object.assign(createBugForm, createInitialBugForm());
};

const submitForm = (): NewBugForm | null => {
    const title = createBugForm.title.trim();
    if (!title) {
        message.warning("请填写标题");
        return null;
    }
    return {
        ...createBugForm,
        collaborators: [...createBugForm.collaborators],
        planTime: [...createBugForm.planTime] as NewBugForm["planTime"],
        tags: [...createBugForm.tags]
    };
};

const handleCancel = () => {
    resetForm();
    emit("close");
};

defineExpose({
    submit: submitForm,
    reset: resetForm,
    cancel: handleCancel
});

onMounted(async () => {
    await loadMemberOptions();
    ownerGroups.value.forEach((g) => {
        createAssigneeGroupOpen[g.label] = false;
    });
    if (ownerGroups.value.length > 0) {
        createAssigneeGroupOpen[ownerGroups.value[0]!.label] = true;
    }
});
</script>

<template>
    <div class="create-bug-drawer">
        <div class="create-bug-main">
            <div class="create-bug-row create-bug-row-full">
                <div class="create-bug-field">
                    <label class="create-bug-label">标题 <span class="required">*</span></label>
                    <vort-input v-model="createBugForm.title" placeholder="请填写" />
                </div>
            </div>

            <div class="create-bug-row">
                <div class="create-bug-field">
                    <label class="create-bug-label">负责人/协作者</label>
                    <div class="bug-detail-info-assignee create-assignee-wrapper w-full" @click.stop>
                        <Popover v-model:open="createAssigneeDropdownOpen" trigger="click" placement="bottomLeft" :arrow="false">
                            <div
                                class="detail-assignee-trigger create-assignee-trigger"
                                :class="createAssigneeDropdownOpen ? 'active' : ''"
                                tabindex="0"
                                @click.stop="toggleCreateAssigneeMenu"
                            >
                                <div class="detail-assignee-split">
                                    <div class="detail-assignee-owner">
                                        <span
                                            v-if="createBugForm.owner"
                                            class="detail-assignee-avatar overflow-hidden"
                                            :style="{ backgroundColor: getAvatarBg(createBugForm.owner) }"
                                        >
                                            <img v-if="getMemberAvatarUrl(createBugForm.owner)" :src="getMemberAvatarUrl(createBugForm.owner)" class="w-full h-full object-cover" />
                                            <template v-else>{{ getAvatarLabel(createBugForm.owner) }}</template>
                                        </span>
                                        <span class="detail-assignee-owner-name" :class="!createBugForm.owner ? 'text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))]' : 'text-[var(--vort-text,rgba(0,0,0,0.88))]'">
                                            {{ createBugForm.owner || "指派负责人/协作者" }}
                                        </span>
                                    </div>
                                    <span v-if="createBugForm.collaborators.length > 0" class="detail-assignee-separator">/</span>
                                    <div v-if="createBugForm.collaborators.length > 0" class="detail-assignee-collaborators detail-collab-stack">
                                        <template v-if="createBugForm.collaborators.length > 0">
                                            <span
                                                v-for="name in createBugForm.collaborators"
                                                :key="'create-collab-' + name"
                                                class="detail-assignee-avatar overflow-hidden"
                                                :style="{ backgroundColor: getAvatarBg(name) }"
                                                :title="name"
                                            >
                                                <img v-if="getMemberAvatarUrl(name)" :src="getMemberAvatarUrl(name)" class="w-full h-full object-cover" />
                                                <template v-else>{{ getAvatarLabel(name) }}</template>
                                            </span>
                                        </template>
                                    </div>
                                </div>
                                <span class="vort-select-arrow ml-auto" :class="{ 'vort-select-arrow-open': createAssigneeDropdownOpen }">
                                    <DownOutlined />
                                </span>
                            </div>

                            <template #content>
                                <div class="detail-assignee-dropdown create-assignee-dropdown">
                                    <div class="mb-2">
                                        <div class="relative">
                                            <VortInput
                                                v-model="createAssigneeKeyword"
                                                placeholder="输入搜索用户名"
                                                class="w-full"
                                                size="small"
                                            />
                                        </div>
                                    </div>
                                    <div class="max-h-[320px] overflow-y-auto -mx-3">
                                        <div v-for="group in filteredCreateAssigneeGroups" :key="'create-assignee-' + group.label">
                                            <VortButton
                                                class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                                variant="text"
                                                @click.stop="toggleCreateAssigneeGroup(group.label)"
                                            >
                                                <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                                <span class="status-arrow-simple" :class="{ open: createAssigneeGroupOpen[group.label] }" />
                                            </VortButton>
                                            <div v-if="createAssigneeGroupOpen[group.label]">
                                                <div
                                                    v-for="member in group.members"
                                                    :key="'create-assignee-member-' + group.label + member"
                                                    class="detail-assignee-row"
                                                >
                                                    <div class="detail-assignee-row-left">
                                                        <span
                                                            class="detail-assignee-avatar overflow-hidden"
                                                            :style="{ backgroundColor: getAvatarBg(member) }"
                                                        >
                                                            <img v-if="getMemberAvatarUrl(member)" :src="getMemberAvatarUrl(member)" class="w-full h-full object-cover" />
                                                            <template v-else>{{ getAvatarLabel(member) }}</template>
                                                        </span>
                                                        <span class="text-sm text-gray-700">{{ member }}</span>
                                                    </div>
                                                    <div class="detail-assignee-row-actions">
                                                        <VortButton
                                                            class="detail-role-btn"
                                                            variant="text"
                                                            :class="isCreateOwner(member) ? 'active' : ''"
                                                            @click.stop="setCreateOwner(member)"
                                                        >
                                                            负责人
                                                        </VortButton>
                                                        <VortButton
                                                            class="detail-role-btn collab"
                                                            variant="text"
                                                            :class="isCreateCollaborator(member) ? 'active' : ''"
                                                            @click.stop="toggleCreateCollaborator(member)"
                                                        >
                                                            协作者
                                                        </VortButton>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </Popover>
                    </div>
                </div>
                <div v-if="!props.type || props.type === '缺陷'" class="create-bug-field">
                    <label class="create-bug-label">类型 <span class="required">*</span></label>
                    <vort-select v-model="createBugForm.type">
                        <vort-select-option value="缺陷">缺陷</vort-select-option>
                        <vort-select-option value="需求">需求</vort-select-option>
                        <vort-select-option value="任务">任务</vort-select-option>
                    </vort-select>
                </div>
            </div>

            <div class="create-bug-row">
                <div class="create-bug-field">
                    <label class="create-bug-label">计划时间</label>
                    <vort-range-picker
                        v-model="createBugPlanTimeModel"
                        value-format="YYYY-MM-DD"
                        format="YYYY-MM-DD"
                        separator="~"
                        :placeholder="['未设置', '未设置']"
                    />
                </div>
                <div class="create-bug-field">
                    <label class="create-bug-label">关联项目</label>
                    <vort-select v-model="createBugForm.project">
                        <vort-select-option v-for="item in projectOptions" :key="item" :value="item">{{ item }}</vort-select-option>
                    </vort-select>
                </div>
            </div>

            <div class="create-bug-row">
                <div class="create-bug-field">
                    <label class="create-bug-label">迭代</label>
                    <vort-select v-model="createBugForm.iteration" placeholder="选择迭代" allow-clear>
                        <vort-select-option v-for="item in iterationOptions" :key="item" :value="item">{{ item }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="create-bug-field">
                    <label class="create-bug-label">版本</label>
                    <vort-select v-model="createBugForm.version" placeholder="选择版本" allow-clear>
                        <vort-select-option v-for="item in versionOptions" :key="item" :value="item">{{ item }}</vort-select-option>
                    </vort-select>
                </div>
            </div>

            <div class="create-bug-row create-bug-row-full">
                <div class="create-bug-field">
                    <label class="create-bug-label">描述</label>
                    <VortEditor v-model="createBugForm.description" placeholder="请填写描述内容" min-height="260px" />
                </div>
            </div>
        </div>

        <div class="create-bug-side">
            <div class="create-bug-field">
                <label class="create-bug-label">优先级</label>
                <Popover v-model:open="createBugPriorityDropdownOpen" trigger="click" placement="bottomLeft" :arrow="false">
                    <div
                        class="create-bug-priority-trigger"
                        :class="createBugPriorityDropdownOpen ? 'active' : ''"
                        tabindex="0"
                        @click.stop="toggleCreateBugPriorityMenu"
                    >
                        <span
                            v-if="createBugForm.priority"
                            class="priority-pill"
                            :class="priorityClassMap[createBugForm.priority]"
                        >
                            {{ priorityLabelMap[createBugForm.priority] }}
                        </span>
                        <span v-else class="text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))]">请选择</span>
                        <span class="vort-select-arrow ml-auto" :class="{ 'vort-select-arrow-open': createBugPriorityDropdownOpen }">
                            <DownOutlined />
                        </span>
                    </div>
                    <template #content>
                        <div class="create-bug-priority-menu w-full">
                            <VortButton
                                v-for="opt in priorityOptions"
                                :key="opt.value"
                                class="create-bug-priority-option"
                                variant="text"
                                :class="createBugForm.priority === opt.value ? 'is-selected' : ''"
                                @click.stop="selectCreateBugPriority(opt.value)"
                            >
                                <span class="priority-pill" :class="priorityClassMap[opt.value]">
                                    {{ opt.label }}
                                </span>
                            </VortButton>
                        </div>
                    </template>
                </Popover>
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">标签</label>
                <Popover v-model:open="createTagDropdownOpen" trigger="click" placement="bottomLeft" :arrow="false">
                    <div
                        class="create-tag-trigger"
                        :class="createTagDropdownOpen ? 'active' : ''"
                        tabindex="0"
                        @click.stop="toggleCreateTagMenu"
                    >
                        <div class="create-tag-preview">
                            <template v-if="createBugForm.tags.length > 0">
                                <span
                                    v-for="tag in createBugForm.tags.slice(0, 3)"
                                    :key="'create-tag-chip-' + tag"
                                    class="px-1.5 py-0.5 rounded text-xs text-white inline-block"
                                    :style="{ backgroundColor: getTagColor(tag) }"
                                >
                                    {{ tag }}
                                </span>
                                <span v-if="createBugForm.tags.length > 3" class="text-gray-400 text-xs">+{{ createBugForm.tags.length - 3 }}</span>
                            </template>
                            <span v-else class="text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))]">选择标签</span>
                        </div>
                        <span class="vort-select-arrow" :class="{ 'vort-select-arrow-open': createTagDropdownOpen }">
                            <DownOutlined />
                        </span>
                    </div>

                    <template #content>
                        <div class="w-full p-3">
                            <div class="mb-2">
                                <div class="relative">
                                    <VortInput
                                        v-model="createTagKeyword"
                                        placeholder="搜索..."
                                        class="w-full"
                                        size="small"
                                    />
                                </div>
                            </div>
                            <div class="max-h-[220px] overflow-y-auto pr-1">
                                <VortButton
                                    v-for="tag in filteredTagOptions"
                                    :key="'create-tag-opt-' + tag"
                                    class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                    variant="text"
                                    @click.stop="toggleCreateTagOption(tag)"
                                >
                                    <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                        <span v-if="createBugForm.tags.includes(tag)">✓</span>
                                    </span>
                                    <span class="w-5 h-5 rounded-full" :style="{ backgroundColor: getTagColor(tag) }" />
                                    <span class="text-sm text-gray-700">{{ tag }}</span>
                                </VortButton>
                            </div>
                        </div>
                    </template>
                </Popover>
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">关联仓库</label>
                <vort-select v-model="createBugForm.repo" placeholder="选择仓库" allow-clear>
                    <vort-select-option v-for="item in repoOptions" :key="item" :value="item">{{ item }}</vort-select-option>
                </vort-select>
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">关联分支</label>
                <vort-select v-model="createBugForm.branch" placeholder="选择分支" allow-clear>
                    <vort-select-option v-for="item in branchOptions" :key="item" :value="item">{{ item }}</vort-select-option>
                </vort-select>
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">实际开始时间</label>
                <vort-date-picker
                    v-model="createBugForm.startAt"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    format="YYYY-MM-DD HH:mm:ss"
                    :show-time="true"
                    placeholder="选择日期时间"
                />
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">实际结束时间</label>
                <vort-date-picker
                    v-model="createBugForm.endAt"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    format="YYYY-MM-DD HH:mm:ss"
                    :show-time="true"
                    placeholder="选择日期时间"
                />
            </div>
            <div class="create-bug-field">
                <label class="create-bug-label">备注说明</label>
                <vort-input v-model="createBugForm.remark" placeholder="测试用备注" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.create-bug-drawer {
    display: flex;
    gap: 32px;
    height: 100%;
}

.create-bug-main {
    flex: 1;
    overflow-y: auto;
    padding-right: 8px;
}

.create-bug-side {
    width: 280px;
    flex-shrink: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.create-bug-row {
    display: flex;
    gap: 24px;
    margin-bottom: 24px;
}

.create-bug-row-full {
    flex-direction: column;
}

.create-bug-field {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.create-bug-field :deep(.vort-popover-trigger) {
    width: 100%;
}

.create-assignee-wrapper :deep(.vort-popover-trigger) {
    width: 100%;
}

.create-bug-side .create-bug-field {
    flex: none;
}

.create-bug-label {
    font-size: 13px;
    font-weight: 500;
    color: #334155;
}

.create-bug-label .required {
    color: #ef4444;
    margin-left: 2px;
}

.bug-detail-info-assignee {
    cursor: pointer;
}

.detail-assignee-trigger {
    display: flex;
    align-items: center;
    padding: 4px 11px;
    border-radius: 6px;
    border: 1px solid transparent;
    width: 100%;
    min-height: 32px;
}

.detail-assignee-trigger:hover,
.detail-assignee-trigger.active {
    background: #f8fafc;
    border-color: #e2e8f0;
}

.create-assignee-trigger {
    border: 1px solid #d9d9d9;
    background: #fff;
    transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
    outline: none;
    cursor: pointer;
}

.create-assignee-trigger:hover,
.create-assignee-trigger.active {
    border-color: var(--vort-primary, #1456f0);
    background: #fff;
}

.create-assignee-trigger:focus-within,
.create-assignee-trigger:focus {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

.detail-assignee-split {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
}

.detail-assignee-owner {
    display: flex;
    align-items: center;
    gap: 6px;
}

.detail-assignee-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    font-size: 11px;
    color: white;
    font-weight: 500;
}

.detail-assignee-owner-name {
    font-size: 14px;
}

.detail-assignee-separator {
    color: #cbd5e1;
    font-size: 14px;
}

.detail-assignee-collaborators {
    display: flex;
    align-items: center;
}

.detail-collab-stack {
    margin-left: -4px;
}

.detail-collab-stack .detail-assignee-avatar {
    margin-left: -6px;
    border: 2px solid white;
}

.detail-assignee-add {
    background: #f1f5f9 !important;
    color: #94a3b8 !important;
    font-size: 14px !important;
    border: 1px dashed #cbd5e1;
}

.detail-assignee-dropdown {
    width: 280px;
    padding: 12px;
}

.detail-assignee-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-radius: 6px;
}

.detail-assignee-row:hover {
    background: #f8fafc;
}

.detail-assignee-row-left {
    display: flex;
    align-items: center;
    gap: 8px;
}

.detail-assignee-row-actions {
    display: flex;
    gap: 4px;
}

.detail-role-btn {
    font-size: 12px !important;
    padding: 4px 8px !important;
    color: #64748b;
}

.detail-role-btn.active {
    color: #3b82f6;
    background: #eff6ff;
}

.detail-role-btn.collab.active {
    color: #8b5cf6;
    background: #f5f3ff;
}

.vort-select-arrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    transition: transform var(--vort-transition-colors, 0.2s);
}

.vort-select-arrow-open {
    transform: rotate(180deg);
}

.ml-auto {
    margin-left: auto;
}

.create-bug-priority-trigger {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    min-height: 32px;
    padding: 4px 11px;
    border-radius: 6px;
    border: 1px solid #d9d9d9;
    background: #fff;
    transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
    outline: none;
    cursor: pointer;
}

.create-bug-priority-trigger:hover,
.create-bug-priority-trigger.active {
    border-color: var(--vort-primary, #1456f0);
}

.create-bug-priority-trigger:focus-within,
.create-bug-priority-trigger:focus {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

.create-bug-priority-menu {
    padding: 8px;
}

.create-bug-priority-option {
    width: 100%;
    justify-content: flex-start !important;
    padding: 8px 12px !important;
}

.create-bug-priority-option.is-selected {
    background: #eff6ff;
}

.priority-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid;
}

.create-tag-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-height: 32px;
    padding: 4px 11px;
    border-radius: 6px;
    border: 1px solid #d9d9d9;
    background: #fff;
    transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
    outline: none;
    cursor: pointer;
}

.create-tag-trigger:hover,
.create-tag-trigger.active {
    border-color: var(--vort-primary, #1456f0);
}

.create-tag-trigger:focus-within,
.create-tag-trigger:focus {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

.create-tag-preview {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
}
</style>

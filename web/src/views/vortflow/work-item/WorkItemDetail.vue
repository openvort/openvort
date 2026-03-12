<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch } from "vue";
import { message } from "@/components/vort";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import WorkItemStatus from "@/components/vort-biz/work-item/WorkItemStatus.vue";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import { Pencil } from "lucide-vue-next";
import { useWorkItemCommon } from "./useWorkItemCommon";
import type { WorkItemType, Status, RowItem, DetailComment, DetailLog } from "@/components/vort-biz/work-item/WorkItemTable.types";

interface Props {
    workNo: string;
    initialData?: RowItem;
    parentRecord?: RowItem | null;
    childRecords?: RowItem[];
}

const props = defineProps<Props>();

const emit = defineEmits<{
    close: [];
    update: [data: Partial<RowItem>];
    delete: [];
    openRelated: [record: RowItem];
    createChild: [record: RowItem];
}>();

const {
    getStatusOptionsByType,
    getStatusOption,
    getAvatarBg,
    getAvatarLabel,
    getMemberAvatarUrl,
    getMemberIdByName,
    loadMemberOptions,
    getWorkItemTypeIconClass,
    getWorkItemTypeIconSymbol,
} = useWorkItemCommon();

const detailCurrentUser = "当前用户";
const loading = ref(false);
const record = ref<RowItem | null>(props.initialData || null);
const detailActiveTab = ref("detail");
const detailBottomTab = ref<"comments" | "logs">("comments");
const detailStatusDropdownOpen = ref(false);
const detailStatusKeyword = ref("");
const detailAssigneeDropdownOpen = ref(false);
const detailAssigneeKeyword = ref("");
const detailAssigneeGroupOpen = reactive<Record<string, boolean>>({});
const detailDescEditing = ref(false);
const detailDescDraft = ref("");
const detailCommentDraft = ref("");
const detailCommentsMap = reactive<Record<string, DetailComment[]>>({});
const detailLogsMap = reactive<Record<string, DetailLog[]>>({});

const detailCurrentRecord = computed(() => record.value);
const parentRecord = computed(() => props.parentRecord || null);
const childRecords = computed(() => props.childRecords || []);
const canCreateChild = computed(() => Boolean(record.value?.backendId) && record.value?.type === "需求");

const detailComments = computed(() => {
    if (!props.workNo) return [];
    return detailCommentsMap[props.workNo] || [];
});

const detailLogs = computed(() => {
    if (!props.workNo) return [];
    return detailLogsMap[props.workNo] || [];
});

const filteredDetailStatusOptions = computed(() => {
    const type = record.value?.type || "缺陷";
    const options = getStatusOptionsByType(type);
    const kw = detailStatusKeyword.value.trim().toLowerCase();
    if (!kw) return options;
    return options.filter((opt) => opt.label.toLowerCase().includes(kw));
});

const filteredDetailAssigneeGroups = computed(() => {
    const groups = [
        { label: "项目成员", members: ["代志祥", "陈艳", "陈曦", "祝璞", "刘洋", "甘洋", "邱锐", "熊纲强"] },
        { label: "企业成员", members: ["apollo_Xuuu", "曾春红", "superdargon", "邱锐", "熊纲强"] },
    ];
    const kw = detailAssigneeKeyword.value.trim();
    if (!kw) return groups;
    return groups
        .map((g) => ({
            ...g,
            members: g.members.filter((m) => m.includes(kw))
        }))
        .filter((g) => g.members.length > 0);
});

const ensureDetailPanelsData = () => {
    if (!detailCommentsMap[props.workNo]) {
        detailCommentsMap[props.workNo] = [];
    }
    if (!detailLogsMap[props.workNo]) {
        detailLogsMap[props.workNo] = [];
    }
};

const appendDetailLog = (action: string) => {
    if (!detailLogsMap[props.workNo]) detailLogsMap[props.workNo] = [];
    const logs = detailLogsMap[props.workNo];
    if (!logs) return;
    logs.unshift({
        id: `${props.workNo}-l-${Date.now()}`,
        actor: detailCurrentUser,
        createdAt: "刚刚",
        action
    });
};

const toggleDetailStatusMenu = () => {
    detailStatusDropdownOpen.value = !detailStatusDropdownOpen.value;
    if (!detailStatusDropdownOpen.value) detailStatusKeyword.value = "";
};

const toggleDetailAssigneeMenu = () => {
    detailAssigneeDropdownOpen.value = !detailAssigneeDropdownOpen.value;
    if (!detailAssigneeDropdownOpen.value) detailAssigneeKeyword.value = "";
};

const toggleDetailAssigneeGroup = (group: string) => {
    detailAssigneeGroupOpen[group] = !detailAssigneeGroupOpen[group];
};

const selectDetailStatus = async (value: Status) => {
    if (!record.value) return;
    const prevStatus = record.value.status;
    record.value.status = value;
    detailStatusDropdownOpen.value = false;
    detailStatusKeyword.value = "";
    appendDetailLog(`将状态修改为"${value}"`);
    emit("update", { status: value });
};

const isDetailOwner = (member: string): boolean => {
    return record.value?.owner === member;
};

const isDetailCollaborator = (member: string): boolean => {
    return (record.value?.collaborators || []).includes(member);
};

const setDetailOwner = async (member: string) => {
    if (!record.value) return;
    const prev = record.value.owner;
    const nextOwner = member || "未指派";
    record.value.owner = nextOwner;
    detailAssigneeDropdownOpen.value = false;
    detailAssigneeKeyword.value = "";
    appendDetailLog(`将负责人修改为"${nextOwner}"`);
    emit("update", { owner: nextOwner });
};

const toggleDetailCollaborator = async (member: string) => {
    if (!record.value) return;
    const collaborators = [...record.value.collaborators];
    const idx = collaborators.indexOf(member);
    if (idx >= 0) {
        collaborators.splice(idx, 1);
        appendDetailLog(`取消协作者"${member}"`);
    } else {
        collaborators.push(member);
        appendDetailLog(`添加协作者"${member}"`);
    }
    record.value.collaborators = collaborators;
    emit("update", { collaborators });
};

const setDetailCollaborators = async (nextCollaborators: string[]) => {
    if (!record.value) return;
    const prev = [...record.value.collaborators];
    record.value.collaborators = [...nextCollaborators];
    try {
        emit("update", { collaborators: [...nextCollaborators] });
    } catch {
        record.value.collaborators = prev;
    }
};

const openDetailDescEditor = () => {
    detailDescDraft.value = record.value?.description || "";
    detailDescEditing.value = true;
};

const saveDetailDescEditor = () => {
    if (!record.value) return;
    record.value.description = detailDescDraft.value;
    detailDescEditing.value = false;
    appendDetailLog("更新了描述");
    emit("update", { description: detailDescDraft.value });
};

const cancelDetailDescEditor = () => {
    detailDescEditing.value = false;
    detailDescDraft.value = "";
};

const submitDetailComment = () => {
    const content = detailCommentDraft.value.trim();
    if (!content) {
        message.warning("请先输入评论内容");
        return;
    }
    if (!detailCommentsMap[props.workNo]) detailCommentsMap[props.workNo] = [];
    const comments = detailCommentsMap[props.workNo];
    if (!comments) return;
    comments.unshift({
        id: `${props.workNo}-c-${Date.now()}`,
        author: detailCurrentUser,
        createdAt: "刚刚",
        content
    });
    detailCommentDraft.value = "";
    appendDetailLog("发布评论");
    message.success("评论已发布");
};

onMounted(async () => {
    await loadMemberOptions();
    detailAssigneeGroupOpen["全部成员"] = true;
    ensureDetailPanelsData();
});

watch(() => props.initialData, (value) => {
    record.value = value || null;
}, { immediate: true });
</script>

<template>
    <div class="bug-detail-drawer">
        <main class="bug-detail-main" v-if="record">
            <div class="bug-detail-meta-top">
                <span class="work-type-icon" :class="getWorkItemTypeIconClass(record.type)">
                    <svg v-if="record.type === '缺陷'" class="work-type-icon-svg" viewBox="0 0 24 24" aria-hidden="true">
                        <circle cx="12" cy="7.5" r="3.2" fill="white" />
                        <rect x="8" y="10.5" width="8" height="9" rx="3.8" fill="white" />
                        <rect x="11.2" y="10.8" width="1.6" height="8.6" rx="0.8" fill="#ef4444" />
                        <path d="M8.3 12.3H5.2M8.1 15.1H4.8M15.9 12.3H18.8M16.1 15.1H19.2" stroke="white" stroke-width="1.5" stroke-linecap="round" />
                        <path d="M10.2 4.8 8.7 3.3M13.8 4.8 15.3 3.3" stroke="white" stroke-width="1.5" stroke-linecap="round" />
                    </svg>
                    <template v-else>{{ getWorkItemTypeIconSymbol(record.type) }}</template>
                </span>
                <span class="bug-detail-no">{{ record.workNo }}</span>
                <WorkItemStatus
                    :model-value="record.status"
                    :options="filteredDetailStatusOptions"
                    :open="detailStatusDropdownOpen"
                    v-model:keyword="detailStatusKeyword"
                    @update:open="(open) => { detailStatusDropdownOpen = open; if (!open) detailStatusKeyword = ''; }"
                    @change="selectDetailStatus"
                >
                    <template #trigger>
                        <VortButton class="detail-status-trigger" variant="text" @click.stop="toggleDetailStatusMenu">
                            <span class="detail-status-content">
                                <span class="detail-status-icon" :class="getStatusOption(record.status, record.type).iconClass">
                                    {{ getStatusOption(record.status, record.type).icon }}
                                </span>
                                <span class="detail-status-text">{{ record.status }}</span>
                            </span>
                            <span class="status-arrow-simple" :class="{ open: detailStatusDropdownOpen }" />
                        </VortButton>
                    </template>
                </WorkItemStatus>
            </div>

            <div v-if="record.type === '需求' && parentRecord" class="story-tree-header">
                <div class="story-parent-node" @click="emit('openRelated', parentRecord)">
                    <span class="work-type-icon-small" :style="{ color: '#64748b' }">
                        <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true" role="img" class="work-type-icon-svg-small" width="1em" height="1em" preserveAspectRatio="xMidYMid meet" viewBox="0 0 16 16">
                            <g fill="none" fill-rule="evenodd">
                                <path d="M0 0h16v16H0z"></path>
                                <path fill="currentColor" fill-rule="nonzero" d="M13.5 1.5a1 1 0 011 1v11a1 1 0 01-1 1h-11a1 1 0 01-1-1v-11a1 1 0 011-1zm-.25 1H2.75a.25.25 0 00-.243.193L2.5 2.75v10.5a.25.25 0 00.193.243l.057.007h10.5a.25.25 0 00.243-.193l.007-.057V2.75a.25.25 0 00-.25-.25zm-7.8 6.05a1.7 1.7 0 110 3.4 1.7 1.7 0 010-3.4zm0 .9a.8.8 0 100 1.6.8.8 0 000-1.6zm6.55.3a.5.5 0 110 1H9a.5.5 0 110-1zM7.736 4.146a.5.5 0 010 .708l-2.122 2.12a.5.5 0 01-.707 0l-1.06-1.06a.5.5 0 11.707-.707l.706.708 1.768-1.769a.5.5 0 01.708 0zM12 5.25a.5.5 0 110 1H9a.5.5 0 110-1z"></path>
                            </g>
                        </svg>
                    </span>
                    <span class="parent-title">{{ parentRecord.title }}</span>
                </div>
                <div class="story-child-node">
                    <div class="tree-line"></div>
                    <h2 class="bug-detail-title" style="margin-bottom: 0;">{{ record.title }}</h2>
                </div>
            </div>
            <h2 v-else class="bug-detail-title">{{ record.title }}</h2>
            <p class="bug-detail-sub" :style="record.type === '需求' && parentRecord ? 'margin-top: 8px;' : ''">
                {{ record.owner || "未指派" }}，创建于 {{ record.createdAt }}，最近更新于 {{ record.createdAt }}
            </p>
            <div class="bug-detail-tabs">
                <button :class="{ active: detailActiveTab === 'detail' }" @click="detailActiveTab = 'detail'">详情</button>
                <button :class="{ active: detailActiveTab === 'worklog' }" @click="detailActiveTab = 'worklog'">工作日志</button>
                <button :class="{ active: detailActiveTab === 'related' }" @click="detailActiveTab = 'related'">关联工作项</button>
                <button :class="{ active: detailActiveTab === 'test' }" @click="detailActiveTab = 'test'">关联测试用例</button>
                <button :class="{ active: detailActiveTab === 'docs' }" @click="detailActiveTab = 'docs'">关联文档</button>
            </div>

            <div class="bug-detail-panel" v-if="detailActiveTab === 'detail'">
                <div class="bug-detail-top-grid">
                    <div class="bug-detail-left-col">
                        <div class="bug-detail-info-item bug-detail-info-item-row bug-detail-info-assignee" @click.stop>
                            <label>负责人 / 协作</label>
                            <WorkItemMemberPicker
                                mode="assignee"
                                :owner="record.owner === '未指派' ? '' : record.owner"
                                :collaborators="record.collaborators"
                                :groups="filteredDetailAssigneeGroups"
                                :open="detailAssigneeDropdownOpen"
                                v-model:keyword="detailAssigneeKeyword"
                                :dropdown-width="280"
                                :dropdown-max-height="320"
                                :bordered="false"
                                :collapsible="false"
                                :get-avatar-bg="getAvatarBg"
                                :get-avatar-label="getAvatarLabel"
                                :get-avatar-url="getMemberAvatarUrl"
                                @update:open="(open) => { detailAssigneeDropdownOpen = open; if (!open) detailAssigneeKeyword = ''; }"
                                @update:owner="setDetailOwner"
                                @update:collaborators="setDetailCollaborators"
                            >
                                <template #trigger>
                                    <VortButton
                                        class="detail-assignee-trigger"
                                        variant="text"
                                        :class="detailAssigneeDropdownOpen ? 'active' : ''"
                                        @click.stop="toggleDetailAssigneeMenu"
                                    >
                                        <div class="detail-assignee-split">
                                            <div class="detail-assignee-owner">
                                                <span
                                                    v-if="record.owner && record.owner !== '未指派'"
                                                    class="detail-assignee-avatar overflow-hidden"
                                                    :style="{ backgroundColor: getAvatarBg(record.owner) }"
                                                >
                                                    <img v-if="getMemberAvatarUrl(record.owner)" :src="getMemberAvatarUrl(record.owner)" class="w-full h-full object-cover" />
                                                    <template v-else>{{ getAvatarLabel(record.owner) }}</template>
                                                </span>
                                                <span class="detail-assignee-owner-name">
                                                    {{ record.owner || "未指派" }}
                                                </span>
                                            </div>
                                            <span class="detail-assignee-separator">/</span>
                                            <div class="detail-assignee-collaborators detail-collab-stack">
                                                <template v-if="record.collaborators.length > 0">
                                                    <span
                                                        v-for="name in record.collaborators"
                                                        :key="'detail-collab-' + name"
                                                        class="detail-assignee-avatar overflow-hidden"
                                                        :style="{ backgroundColor: getAvatarBg(name) }"
                                                        :title="name"
                                                    >
                                                        <img v-if="getMemberAvatarUrl(name)" :src="getMemberAvatarUrl(name)" class="w-full h-full object-cover" />
                                                        <template v-else>{{ getAvatarLabel(name) }}</template>
                                                    </span>
                                                </template>
                                                <span v-else class="detail-assignee-avatar detail-assignee-add">+</span>
                                            </div>
                                        </div>
                                    </VortButton>
                                </template>
                            </WorkItemMemberPicker>
                        </div>
                        <div class="bug-detail-info-item bug-detail-info-item-row"><label>计划时间</label><div>{{ record.planTime[0] }} ~ {{ record.planTime[1] }}</div></div>
                        <div class="bug-detail-info-item bug-detail-info-item-row"><label>迭代</label><div>未设置</div></div>
                    </div>
                    <div class="bug-detail-right-col">
                        <div class="bug-detail-info-item bug-detail-info-item-row"><label>类型</label><div>{{ record.type }}</div></div>
                        <div class="bug-detail-info-item bug-detail-info-item-row"><label>项目</label><div>VortMall</div></div>
                        <div class="bug-detail-info-item bug-detail-info-item-row"><label>版本</label><div>未设置</div></div>
                    </div>
                </div>

                <!-- 子需求栏目 -->
                <div class="bug-detail-sub-items" v-if="record.type === '需求'">
                    <div class="bug-detail-sub-items-head">
                        <div class="flex items-center gap-2">
                            <h4>子需求</h4>
                            <span class="count">{{ childRecords.length }}</span>
                        </div>
                        <VortButton
                            class="add-sub-item-btn"
                            variant="text"
                            size="small"
                            :disabled="!canCreateChild"
                            @click="record && emit('createChild', record)"
                        >
                            <span class="icon">+</span> 添加子需求
                        </VortButton>
                    </div>
                    
                    <div class="bug-detail-sub-items-content">
                        <div v-if="childRecords.length === 0" class="bug-detail-sub-items-empty">
                            <span class="empty-text">暂无关联的子需求</span>
                        </div>
                        <div v-else class="bug-detail-sub-items-list">
                            <div 
                                v-for="child in childRecords" 
                                :key="child.backendId || child.workNo"
                                class="bug-detail-sub-item group"
                                @click="emit('openRelated', child)"
                            >
                                <div class="sub-item-left">
                                    <span class="work-type-icon-small text-indigo-500">
                                        <svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" role="img" width="1em" height="1em" viewBox="0 0 16 16">
                                            <g fill="none" fill-rule="evenodd">
                                                <path d="M0 0h16v16H0z"></path>
                                                <path fill="currentColor" fill-rule="nonzero" d="M13.5 1.5a1 1 0 011 1v11a1 1 0 01-1 1h-11a1 1 0 01-1-1v-11a1 1 0 011-1zm-.25 1H2.75a.25.25 0 00-.243.193L2.5 2.75v10.5a.25.25 0 00.193.243l.057.007h10.5a.25.25 0 00.243-.193l.007-.057V2.75a.25.25 0 00-.25-.25zm-7.8 6.05a1.7 1.7 0 110 3.4 1.7 1.7 0 010-3.4zm0 .9a.8.8 0 100 1.6.8.8 0 000-1.6zm6.55.3a.5.5 0 110 1H9a.5.5 0 110-1zM7.736 4.146a.5.5 0 010 .708l-2.122 2.12a.5.5 0 01-.707 0l-1.06-1.06a.5.5 0 11.707-.707l.706.708 1.768-1.769a.5.5 0 01.708 0zM12 5.25a.5.5 0 110 1H9a.5.5 0 110-1z"></path>
                                            </g>
                                        </svg>
                                    </span>
                                    <span class="sub-item-no">{{ child.workNo }}</span>
                                    <span class="sub-item-title group-hover:text-blue-600">{{ child.title }}</span>
                                </div>
                                <div class="sub-item-right">
                                    <div class="sub-item-owner">
                                        <span class="detail-assignee-avatar overflow-hidden" :style="{ backgroundColor: getAvatarBg(child.owner || '未指派'), width: '20px', height: '20px', fontSize: '10px' }">
                                            <img v-if="getMemberAvatarUrl(child.owner || '')" :src="getMemberAvatarUrl(child.owner || '')" class="w-full h-full object-cover" />
                                            <template v-else>{{ getAvatarLabel(child.owner || '未指派') }}</template>
                                        </span>
                                        <span class="owner-name">{{ child.owner || '未指派' }}</span>
                                    </div>
                                    <div class="sub-item-status">
                                        <span class="status-icon" :class="getStatusOption(child.status, child.type).iconClass">{{ getStatusOption(child.status, child.type).icon }}</span>
                                        <span class="status-text">{{ child.status }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="bug-detail-desc">
                    <div class="bug-detail-desc-head">
                        <h4>描述</h4>
                        <VortButton class="bug-detail-desc-edit-btn" variant="text" size="small" @click="openDetailDescEditor">
                            <Pencil :size="14" />
                        </VortButton>
                    </div>
                    <template v-if="detailDescEditing">
                        <VortEditor v-model="detailDescDraft" placeholder="请输入描述内容..." min-height="300px" />
                        <div class="bug-detail-desc-actions">
                            <vort-button variant="primary" @click="saveDetailDescEditor">保存</vort-button>
                            <vort-button @click="cancelDetailDescEditor">取消</vort-button>
                        </div>
                    </template>
                    <template v-else>
                        <div v-if="(record.description || '').trim()" class="bug-detail-desc-content">
                            <MarkdownView :content="record.description || ''" />
                        </div>
                        <div v-else class="bug-detail-desc-content">-</div>
                    </template>
                </div>

                <div class="bug-detail-bottom-panel">
                    <div class="bug-detail-bottom-tabs">
                        <button
                            :class="{ active: detailBottomTab === 'comments' }"
                            @click="detailBottomTab = 'comments'"
                        >
                            评论
                            <span class="count">{{ detailComments.length }}</span>
                        </button>
                        <button
                            :class="{ active: detailBottomTab === 'logs' }"
                            @click="detailBottomTab = 'logs'"
                        >
                            操作日志
                            <span class="count">{{ detailLogs.length }}</span>
                        </button>
                    </div>

                    <div v-if="detailBottomTab === 'comments'" class="bug-detail-comments">
                        <div v-if="detailComments.length === 0" class="bug-detail-empty">暂无评论</div>
                        <div v-else class="bug-detail-comment-list">
                            <div v-for="item in detailComments" :key="item.id" class="bug-detail-comment-item">
                                <span class="bug-detail-comment-avatar">{{ item.author.slice(0, 1) }}</span>
                                <div class="bug-detail-comment-main">
                                    <div class="bug-detail-comment-meta">
                                        <span class="author">{{ item.author }}</span>
                                        <span class="time">{{ item.createdAt }}</span>
                                    </div>
                                    <div class="bug-detail-comment-content">{{ item.content }}</div>
                                </div>
                            </div>
                        </div>

                        <div class="bug-detail-comment-editor">
                            <VortEditor v-model="detailCommentDraft" placeholder="发表您的看法（Ctrl/Command+Enter发送）" min-height="120px" />
                            <div class="bug-detail-desc-actions">
                                <vort-button variant="primary" @click="submitDetailComment">评论</vort-button>
                                <vort-button @click="detailCommentDraft = ''">取消</vort-button>
                            </div>
                        </div>
                    </div>

                    <div v-else class="bug-detail-logs">
                        <div v-if="detailLogs.length === 0" class="bug-detail-empty">暂无操作日志</div>
                        <div v-else class="bug-detail-log-list">
                            <div v-for="item in detailLogs" :key="item.id" class="bug-detail-log-item">
                                <span class="bug-detail-log-dot" />
                                <span class="actor">{{ item.actor }}</span>
                                <span class="action">{{ item.action }}</span>
                                <span class="time">{{ item.createdAt }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bug-detail-panel" v-else-if="detailActiveTab === 'worklog'">
                <p class="bug-detail-empty">暂无工作日志</p>
            </div>
            <div class="bug-detail-panel" v-else-if="detailActiveTab === 'related'">
                <template v-if="record.type === '需求' && childRecords.length > 0">
                    <div class="story-children-list">
                        <button
                            v-for="child in childRecords"
                            :key="child.backendId || child.workNo"
                            type="button"
                            class="story-children-item"
                            @click="emit('openRelated', child)"
                        >
                            <span class="story-children-title">{{ child.title }}</span>
                            <span class="story-children-status">{{ child.status }}</span>
                        </button>
                    </div>
                </template>
                <p v-else class="bug-detail-empty">暂无关联工作项</p>
            </div>
            <div class="bug-detail-panel" v-else-if="detailActiveTab === 'test'">
                <p class="bug-detail-empty">暂无关联测试用例</p>
            </div>
            <div class="bug-detail-panel" v-else>
                <p class="bug-detail-empty">暂无关联文档</p>
            </div>
        </main>
        <div v-else class="p-4 text-center text-gray-500">加载中...</div>
    </div>
</template>

<style scoped>
.bug-detail-drawer {
    height: 100%;
}

.bug-detail-main {
    padding: 0 4px;
}

.bug-detail-meta-top {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}

.work-type-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    font-size: 18px;
}

.work-type-icon-demand {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: white;
}

.work-type-icon-task {
    background: linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%);
    color: white;
}

.work-type-icon-bug {
    background: linear-gradient(135deg, #ef4444 0%, #f97316 100%);
    color: white;
}

.work-type-icon-svg {
    width: 20px;
    height: 20px;
}

.bug-detail-no {
    font-size: 14px;
    color: #64748b;
    font-weight: 500;
}

.detail-status-trigger {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border-radius: 4px;
}

.detail-status-content {
    display: flex;
    align-items: center;
    gap: 4px;
}

.detail-status-icon {
    font-size: 14px;
}

.detail-status-text {
    font-size: 14px;
    color: #334155;
}

.status-arrow-simple {
    display: inline-block;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid #94a3b8;
    transition: transform 0.2s;
}

.status-arrow-simple.open {
    transform: rotate(180deg);
}

.bug-detail-title {
    font-size: 20px;
    font-weight: 600;
    color: #1e293b;
    margin: 0 0 8px 0;
    line-height: 1.4;
}

.bug-detail-sub {
    font-size: 13px;
    color: #64748b;
    margin: 0 0 20px 0;
}

.story-tree-header {
    margin-bottom: 8px;
}

.story-parent-node {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #64748b;
    cursor: pointer;
    font-size: 14px;
    transition: color 0.2s;
}

.story-parent-node:hover {
    color: #3b82f6;
}

.work-type-icon-small {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
}

.work-type-icon-svg-small {
    width: 16px;
    height: 16px;
}

.parent-title {
    max-width: 400px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.story-child-node {
    display: flex;
    align-items: flex-start;
    margin-top: 4px;
}

.tree-line {
    width: 16px;
    height: 20px;
    border-left: 1.5px solid #cbd5e1;
    border-bottom: 1.5px solid #cbd5e1;
    border-bottom-left-radius: 6px;
    margin-left: 7px;
    margin-right: 8px;
    margin-top: -4px;
    flex-shrink: 0;
}

.bug-detail-tabs {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 20px;
}

.bug-detail-tabs button {
    padding: 10px 16px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: #64748b;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
}

.bug-detail-tabs button:hover {
    color: #334155;
}

.bug-detail-tabs button.active {
    color: #3b82f6;
    border-bottom-color: #3b82f6;
}

.bug-detail-top-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px 48px;
    margin-bottom: 24px;
}

.bug-detail-left-col,
.bug-detail-right-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.bug-detail-info-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.bug-detail-info-item label {
    font-size: 13px;
    color: #64748b;
    font-weight: 400;
}

.bug-detail-info-item > div {
    font-size: 14px;
    color: #1e293b;
}

.bug-detail-info-item-row {
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    min-height: 32px;
}

.bug-detail-info-item-row label {
    flex-shrink: 0;
    width: 100px;
}

.bug-detail-info-assignee {
    cursor: pointer;
}

/* 子需求栏目样式 */
.bug-detail-sub-items {
    margin-bottom: 24px;
}

.bug-detail-sub-items-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}

.bug-detail-sub-items-head h4 {
    font-size: 14px;
    font-weight: 600;
    color: #334155;
    margin: 0;
}

.bug-detail-sub-items-head .count {
    background: #f1f5f9;
    color: #64748b;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}

.add-sub-item-btn {
    color: #3b82f6 !important;
    font-size: 13px !important;
    padding: 4px 8px !important;
    height: auto !important;
}

.add-sub-item-btn:hover {
    background: #eff6ff !important;
}

.add-sub-item-btn .icon {
    margin-right: 4px;
    font-size: 16px;
    line-height: 1;
}

.bug-detail-sub-items-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px 0;
    background: rgba(248, 250, 252, 0.5);
    border: 1px dashed #e2e8f0;
    border-radius: 8px;
}

.bug-detail-sub-items-empty .empty-text {
    color: #94a3b8;
    font-size: 13px;
}

.bug-detail-sub-items-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.bug-detail-sub-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    background: #ffffff;
    border: 1px solid #f1f5f9;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.bug-detail-sub-item:hover {
    border-color: #bfdbfe;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.sub-item-left {
    display: flex;
    align-items: center;
    gap: 12px;
    overflow: hidden;
}

.sub-item-no {
    font-size: 12px;
    font-weight: 500;
    color: #94a3b8;
    flex-shrink: 0;
}

.sub-item-title {
    font-size: 13px;
    color: #334155;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: color 0.2s;
}

.sub-item-right {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0;
    margin-left: 16px;
}

.sub-item-owner {
    display: flex;
    align-items: center;
    gap: 6px;
}

.sub-item-owner .owner-name {
    font-size: 12px;
    color: #64748b;
}

.sub-item-status {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    background: #f8fafc;
    border: 1px solid #f1f5f9;
    border-radius: 4px;
    min-width: 72px;
    justify-content: center;
}

.sub-item-status .status-icon {
    font-size: 12px;
    line-height: 1;
}

.sub-item-status .status-text {
    font-size: 12px;
    color: #475569;
}

.detail-assignee-trigger {
    display: flex;
    align-items: center;
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid transparent;
    margin-left: -10px;
}

.detail-assignee-trigger:hover,
.detail-assignee-trigger.active {
    background: #f8fafc;
    border-color: #e2e8f0;
}

.detail-assignee-split {
    display: flex;
    align-items: center;
    gap: 8px;
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
    font-size: 13px;
    color: #334155;
}

.detail-assignee-separator {
    color: #cbd5e1;
    font-size: 15px;
    margin: 0 6px;
}

.detail-assignee-collaborators {
    display: flex;
    align-items: center;
    gap: 4px;
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

.bug-detail-desc {
    margin-bottom: 24px;
}

.bug-detail-desc-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}

.bug-detail-desc-head h4 {
    font-size: 14px;
    font-weight: 600;
    color: #334155;
    margin: 0;
}

.bug-detail-desc-edit-btn {
    opacity: 0;
    transition: opacity 0.2s;
}

.bug-detail-desc:hover .bug-detail-desc-edit-btn {
    opacity: 1;
}

.bug-detail-desc-content {
    font-size: 14px;
    color: #475569;
    line-height: 1.6;
    padding: 12px;
    background: #f8fafc;
    border-radius: 8px;
    min-height: 60px;
}

.bug-detail-desc-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
}

.bug-detail-bottom-panel {
    border-top: 1px solid #e2e8f0;
    padding-top: 20px;
}

.bug-detail-bottom-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 16px;
}

.bug-detail-bottom-tabs button {
    padding: 8px 12px;
    background: none;
    border: none;
    border-radius: 6px;
    color: #64748b;
    font-size: 13px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
}

.bug-detail-bottom-tabs button:hover {
    background: #f1f5f9;
}

.bug-detail-bottom-tabs button.active {
    background: #eff6ff;
    color: #3b82f6;
}

.bug-detail-bottom-tabs .count {
    background: #e2e8f0;
    padding: 2px 6px;
    border-radius: 10px;
    font-size: 11px;
}

.bug-detail-bottom-tabs button.active .count {
    background: #dbeafe;
}

.bug-detail-empty {
    text-align: center;
    padding: 40px;
    color: #94a3b8;
    font-size: 14px;
}

.story-children-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.story-children-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
    padding: 12px 14px;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    background: #fff;
    text-align: left;
}

.story-children-item:hover {
    border-color: #c7d2fe;
    background: #f8faff;
}

.story-children-title {
    color: #111827;
    font-size: 14px;
}

.story-children-status {
    color: #6b7280;
    font-size: 12px;
    white-space: nowrap;
}

.bug-detail-comment-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 20px;
}

.bug-detail-comment-item {
    display: flex;
    gap: 12px;
}

.bug-detail-comment-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 500;
    flex-shrink: 0;
}

.bug-detail-comment-main {
    flex: 1;
}

.bug-detail-comment-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.bug-detail-comment-meta .author {
    font-size: 13px;
    font-weight: 500;
    color: #334155;
}

.bug-detail-comment-meta .time {
    font-size: 12px;
    color: #94a3b8;
}

.bug-detail-comment-content {
    font-size: 14px;
    color: #475569;
    line-height: 1.5;
}

.bug-detail-comment-editor {
    border-top: 1px solid #e2e8f0;
    padding-top: 16px;
}

.bug-detail-log-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.bug-detail-log-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
}

.bug-detail-log-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #cbd5e1;
    flex-shrink: 0;
}

.bug-detail-log-item .actor {
    font-weight: 500;
    color: #334155;
}

.bug-detail-log-item .action {
    color: #64748b;
}

.bug-detail-log-item .time {
    color: #94a3b8;
    margin-left: auto;
}
</style>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Pencil } from "lucide-vue-next";
import { getVortflowTestCase, getVortflowComments, getVortflowActivity } from "@/api";

interface Props {
    open: boolean;
    caseId: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
    "update:open": [val: boolean];
    edit: [id: string];
}>();

const CASE_TYPE_LABELS: Record<string, string> = {
    functional: "功能测试",
    performance: "性能测试",
    api: "接口测试",
    ui: "UI 测试",
    security: "安全测试",
};

interface CaseDetail {
    id: string;
    title: string;
    module_path: string;
    module_name: string;
    precondition: string;
    notes: string;
    case_type: string;
    priority: number;
    maintainer_name: string;
    steps: { order: number; description: string; expected_result: string }[];
    created_at: string;
    updated_at: string;
    linked_work_item_count: number;
}

const loading = ref(false);
const detail = ref<CaseDetail | null>(null);
const activeTab = ref("detail");

const comments = ref<any[]>([]);
const activities = ref<any[]>([]);

const loadDetail = async () => {
    if (!props.caseId) return;
    loading.value = true;
    try {
        const res = await getVortflowTestCase(props.caseId) as any;
        if (res?.error) return;
        detail.value = res;
    } catch { detail.value = null; }
    finally { loading.value = false; }
};

const loadComments = async () => {
    if (!props.caseId) return;
    try {
        const res = await getVortflowComments("testcase", props.caseId) as any;
        comments.value = res?.items || [];
    } catch { comments.value = []; }
};

const ACTION_LABEL_MAP: Record<string, string> = {
    created: "创建了测试用例", updated: "更新了测试用例", deleted: "删除了测试用例",
    comment_added: "添加了评论", comment_updated: "修改了评论", comment_deleted: "删除了评论",
    link_added: "添加了关联工作项", link_removed: "移除了关联工作项",
};

const formatAction = (action: string) => ACTION_LABEL_MAP[action] || action;

const loadActivities = async () => {
    if (!props.caseId) return;
    try {
        const res = await getVortflowActivity("testcase", props.caseId) as any;
        activities.value = res?.items || [];
    } catch { activities.value = []; }
};

const handleClose = () => { emit("update:open", false); };
const handleEdit = () => { if (detail.value) emit("edit", detail.value.id); };

watch(() => props.open, (val) => {
    if (val && props.caseId) {
        activeTab.value = "detail";
        loadDetail();
    }
});
</script>

<template>
    <vort-drawer :open="open" :width="700" @update:open="handleClose">
        <template #title>
            <div class="tc-detail-header">
                <div v-if="detail?.module_path" class="tc-detail-breadcrumb">{{ detail.module_path }}</div>
                <div class="tc-detail-title-row">
                    <h3 class="tc-detail-title">{{ detail?.title }}</h3>
                    <button class="tc-detail-edit-btn" @click="handleEdit" title="编辑">
                        <Pencil :size="14" />
                    </button>
                </div>
            </div>
        </template>

        <vort-spin :spinning="loading">
            <div v-if="detail" class="tc-detail-body">
                <div class="tc-detail-content">
                    <!-- Tabs -->
                    <div class="tc-detail-tabs">
                        <button :class="{ active: activeTab === 'detail' }" @click="activeTab = 'detail'">用例详情</button>
                        <button :class="{ active: activeTab === 'comments' }" @click="activeTab = 'comments'; loadComments()">评论</button>
                        <button :class="{ active: activeTab === 'activity' }" @click="activeTab = 'activity'; loadActivities()">操作日志</button>
                    </div>

                    <!-- Detail Tab -->
                    <div v-if="activeTab === 'detail'" class="tc-detail-section">
                        <div class="tc-detail-field">
                            <label>前置条件</label>
                            <div class="tc-detail-value">{{ detail.precondition || "暂无内容" }}</div>
                        </div>

                        <div class="tc-detail-field">
                            <label>用例步骤</label>
                            <div v-if="detail.steps && detail.steps.length > 0" class="tc-steps-wrap">
                                <div class="tc-steps-view">
                                    <div class="tc-steps-view-header">
                                        <span class="tc-sv-order">顺序</span>
                                        <span class="tc-sv-desc">步骤描述</span>
                                        <span class="tc-sv-expect">预期结果</span>
                                    </div>
                                    <div v-for="step in detail.steps" :key="step.order" class="tc-steps-view-row">
                                        <span class="tc-sv-order">{{ step.order }}</span>
                                        <span class="tc-sv-desc">{{ step.description }}</span>
                                        <span class="tc-sv-expect">{{ step.expected_result }}</span>
                                    </div>
                                </div>
                            </div>
                            <div v-else class="tc-detail-value">暂无步骤</div>
                        </div>

                        <div class="tc-detail-field">
                            <label>备注</label>
                            <div class="tc-detail-value">{{ detail.notes || "暂无内容" }}</div>
                        </div>
                    </div>

                    <!-- Comments Tab -->
                    <div v-else-if="activeTab === 'comments'" class="tc-detail-section">
                        <p v-if="comments.length === 0" class="tc-detail-empty">暂无评论</p>
                        <div v-else v-for="c in comments" :key="c.id" class="tc-comment-item">
                            <span class="tc-comment-author">{{ c.author_name || "匿名" }}</span>
                            <span class="tc-comment-time">{{ c.created_at?.slice(0, 16) }}</span>
                            <p class="tc-comment-content">{{ c.content }}</p>
                        </div>
                    </div>

                    <!-- Activity Tab -->
                    <div v-else-if="activeTab === 'activity'" class="tc-detail-section">
                        <p v-if="activities.length === 0" class="tc-detail-empty">暂无操作日志</p>
                        <div v-else v-for="a in activities" :key="a.id" class="tc-activity-item">
                            <span class="tc-activity-actor">{{ a.actor_name || "系统" }}</span>
                            <span class="tc-activity-action">{{ formatAction(a.action) }}</span>
                            <span class="tc-activity-time">{{ a.created_at?.slice(0, 16) }}</span>
                        </div>
                    </div>
                </div>

                <!-- Right Sidebar -->
                <div class="tc-detail-sidebar">
                    <div class="tc-detail-meta">
                        <label>功能模块</label>
                        <span>{{ detail.module_name || "未分类" }}</span>
                    </div>
                    <div class="tc-detail-meta">
                        <label>用例类型</label>
                        <span>{{ CASE_TYPE_LABELS[detail.case_type] || detail.case_type }}</span>
                    </div>
                    <div class="tc-detail-meta">
                        <label>优先级</label>
                        <vort-tag :color="{ 0: 'red', 1: 'orange', 2: 'blue', 3: 'default' }[detail.priority] || 'default'" size="small">
                            P{{ detail.priority }}
                        </vort-tag>
                    </div>
                    <div class="tc-detail-meta">
                        <label>维护人</label>
                        <span>{{ detail.maintainer_name || "未指定" }}</span>
                    </div>
                    <div class="tc-detail-meta">
                        <label>创建时间</label>
                        <span>{{ detail.created_at?.slice(0, 10) }}</span>
                    </div>
                    <div class="tc-detail-meta">
                        <label>更新时间</label>
                        <span>{{ detail.updated_at?.slice(0, 10) }}</span>
                    </div>
                </div>
            </div>
        </vort-spin>
    </vort-drawer>
</template>

<style scoped>
.tc-detail-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.tc-detail-breadcrumb {
    font-size: 12px;
    color: var(--vort-text-tertiary);
}

.tc-detail-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
}

.tc-detail-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--vort-text);
    margin: 0;
}

.tc-detail-edit-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    color: var(--vort-text-tertiary);
    background: none;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.tc-detail-edit-btn:hover {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
}

.tc-detail-body {
    display: flex;
    gap: 24px;
}

.tc-detail-content {
    flex: 1;
    min-width: 0;
}

.tc-detail-sidebar {
    width: 180px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.tc-detail-meta label {
    display: block;
    font-size: 12px;
    color: var(--vort-text-tertiary);
    margin-bottom: 4px;
}

.tc-detail-meta span {
    font-size: 13px;
    color: var(--vort-text);
}

/* Tabs */
.tc-detail-tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--vort-border-secondary, #f0f0f0);
    margin-bottom: 16px;
}

.tc-detail-tabs button {
    padding: 8px 16px;
    font-size: 13px;
    color: var(--vort-text-secondary);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
}

.tc-detail-tabs button:hover {
    color: var(--vort-text);
}

.tc-detail-tabs button.active {
    color: var(--vort-primary);
    border-bottom-color: var(--vort-primary);
    font-weight: 500;
}

/* Detail fields */
.tc-detail-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.tc-detail-field label {
    display: block;
    font-size: 12px;
    color: var(--vort-text-tertiary);
    margin-bottom: 6px;
    font-weight: 500;
}

.tc-detail-value {
    font-size: 13px;
    color: var(--vort-text);
    white-space: pre-wrap;
    line-height: 1.6;
}

.tc-detail-empty {
    font-size: 13px;
    color: var(--vort-text-tertiary);
    text-align: center;
    padding: 24px 0;
}

/* Steps view */
.tc-steps-wrap {
    border: 1px solid var(--vort-border-secondary, #f0f0f0);
    border-radius: 6px;
    overflow: hidden;
}

.tc-steps-view {
    display: table;
    width: 100%;
    table-layout: fixed;
    border-collapse: collapse;
}

.tc-steps-view-header {
    display: table-row;
    background: var(--vort-bg-secondary, #fafafa);
    font-size: 12px;
    color: var(--vort-text-secondary);
    font-weight: 500;
}

.tc-steps-view-row {
    display: table-row;
    font-size: 13px;
    color: var(--vort-text);
}

.tc-steps-view-row .tc-sv-order,
.tc-steps-view-row .tc-sv-desc,
.tc-steps-view-row .tc-sv-expect {
    border-top: 1px solid var(--vort-border-secondary, #f0f0f0);
}

.tc-sv-order {
    display: table-cell;
    width: 48px;
    text-align: center;
    padding: 8px 4px;
    vertical-align: top;
}

.tc-sv-desc {
    display: table-cell;
    padding: 8px;
    border-left: 1px solid var(--vort-border-secondary, #f0f0f0);
    word-break: break-word;
    vertical-align: top;
}

.tc-sv-expect {
    display: table-cell;
    padding: 8px;
    border-left: 1px solid var(--vort-border-secondary, #f0f0f0);
    word-break: break-word;
    vertical-align: top;
}

/* Comments */
.tc-comment-item {
    padding: 10px 0;
    border-bottom: 1px solid var(--vort-border-secondary, #f0f0f0);
}

.tc-comment-author {
    font-size: 13px;
    font-weight: 500;
    color: var(--vort-text);
    margin-right: 8px;
}

.tc-comment-time {
    font-size: 12px;
    color: var(--vort-text-tertiary);
}

.tc-comment-content {
    font-size: 13px;
    color: var(--vort-text);
    margin-top: 4px;
}

/* Activity */
.tc-activity-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid var(--vort-border-secondary, #f0f0f0);
    font-size: 13px;
}

.tc-activity-actor { color: var(--vort-text); font-weight: 500; }
.tc-activity-action { color: var(--vort-text-secondary); }
.tc-activity-time { color: var(--vort-text-tertiary); font-size: 12px; margin-left: auto; }
</style>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { z } from "zod";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeft, ListChecks, CheckSquare, Bug, Users, Plus, Trash2, FolderGit2, TerminalSquare, ExternalLink } from "lucide-vue-next";
import {
    getVortflowProject, getVortflowStats, getVortflowStories,
    getVortflowTasks, getVortflowBugs, getVortflowProjectMembers,
    addVortflowProjectMember, removeVortflowProjectMember,
    getVortgitRepos, getVortgitCodeTasks,
} from "@/api";

const route = useRoute();
const router = useRouter();
const projectId = computed(() => route.params.id as string);

const loading = ref(true);
const project = ref<any>({});
const stats = ref({ stories: { total: 0, done: 0 }, tasks: { total: 0, done: 0 }, bugs: { total: 0, closed: 0 } });
const stories = ref<any[]>([]);
const tasks = ref<any[]>([]);
const bugs = ref<any[]>([]);
const members = ref<any[]>([]);
const repos = ref<any[]>([]);
const codeTasks = ref<any[]>([]);

const repoTypeColorMap: Record<string, string> = {
    frontend: "blue", backend: "green", mobile: "purple", docs: "cyan", infra: "orange", other: "default"
};
const repoTypeLabels: Record<string, string> = {
    frontend: "前端", backend: "后端", mobile: "移动端", docs: "文档", infra: "基础设施", other: "其他"
};

const stateColorMap: Record<string, string> = {
    intake: "default", review: "processing", rejected: "red", pm_refine: "orange",
    design: "cyan", breakdown: "purple", dev_assign: "geekblue", in_progress: "blue",
    testing: "orange", bugfix: "volcano", done: "green",
    todo: "default", closed: "default",
    open: "red", confirmed: "orange", fixing: "processing",
    resolved: "cyan", verified: "green",
};

const stateLabels: Record<string, string> = {
    intake: "意向", review: "评审", rejected: "已驳回", pm_refine: "产品完善",
    design: "UI 设计", breakdown: "拆分估时", dev_assign: "分配开发",
    in_progress: "进行中", testing: "测试中", bugfix: "Bug 修复", done: "已完成",
    todo: "待办", closed: "已关闭",
    open: "打开", confirmed: "已确认", fixing: "修复中",
    resolved: "已解决", verified: "已验证",
};

const stateLabel = (val: string) => stateLabels[val] || val;

const loadData = async () => {
    loading.value = true;
    try {
        const [projRes, statsRes, storiesRes, tasksRes, bugsRes, membersRes, reposRes] = await Promise.all([
            getVortflowProject(projectId.value),
            getVortflowStats(projectId.value),
            getVortflowStories({ project_id: projectId.value, page: 1, page_size: 10 }),
            getVortflowTasks({ page: 1, page_size: 10 }),
            getVortflowBugs({ page: 1, page_size: 10 }),
            getVortflowProjectMembers(projectId.value),
            getVortgitRepos({ project_id: projectId.value, page: 1, page_size: 20 }).catch(() => ({ items: [] })),
        ]);
        project.value = projRes || {};
        if (statsRes) {
            const r = statsRes as any;
            stats.value = {
                stories: r.stories ?? { total: 0, done: 0 },
                tasks: r.tasks ?? { total: 0, done: 0 },
                bugs: r.bugs ?? { total: 0, closed: 0 },
            };
        }
        stories.value = (storiesRes as any)?.items || [];
        tasks.value = (tasksRes as any)?.items || [];
        bugs.value = (bugsRes as any)?.items || [];
        members.value = (membersRes as any)?.items || [];
        repos.value = (reposRes as any)?.items || [];

        // Load code tasks for all repos in this project
        const repoIds = repos.value.map((r: any) => r.id);
        if (repoIds.length > 0) {
            try {
                const allTasks: any[] = [];
                for (const rid of repoIds.slice(0, 5)) {
                    const ct: any = await getVortgitCodeTasks({ repo_id: rid, page: 1, page_size: 10 });
                    allTasks.push(...(ct.items || []));
                }
                allTasks.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
                codeTasks.value = allTasks.slice(0, 10);
            } catch { codeTasks.value = []; }
        }
    } catch { /* silent */ }
    finally { loading.value = false; }
};

// Member management
const memberDialogVisible = ref(false);
const newMemberId = ref("");
const newMemberRole = ref("member");
const memberFormRef = ref();

const memberValidationSchema = z.object({
    member_id: z.string().min(1, '成员 ID 不能为空'),
    role: z.string().optional(),
});

const memberFormData = computed(() => ({
    member_id: newMemberId.value,
    role: newMemberRole.value,
}));

const handleAddMember = async () => {
    try { await memberFormRef.value?.validate(); } catch { return; }
    await addVortflowProjectMember(projectId.value, { member_id: newMemberId.value, role: newMemberRole.value });
    newMemberId.value = "";
    memberDialogVisible.value = false;
    const res = await getVortflowProjectMembers(projectId.value);
    members.value = (res as any)?.items || [];
};

const handleRemoveMember = async (memberId: string) => {
    await removeVortflowProjectMember(projectId.value, memberId);
    const res = await getVortflowProjectMembers(projectId.value);
    members.value = (res as any)?.items || [];
};

const codeTaskStatusColor = (s: string) => {
    if (s === "success") return "success";
    if (s === "review") return "warning";
    if (s === "failed") return "error";
    if (s === "running") return "processing";
    return "default";
};

const codeTaskStatusLabel = (s: string) => {
    const m: Record<string, string> = { pending: "等待中", running: "执行中", success: "成功", failed: "失败", review: "待审核" };
    return m[s] || s;
};

const repoNameById = (id: string) => {
    const r = repos.value.find((r: any) => r.id === id);
    return r ? r.full_name || r.name : id;
};

const formatTime = (iso: string | null) => {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("zh-CN"); } catch { return iso; }
};

const goBack = () => router.push("/vortflow/board");

onMounted(loadData);
</script>

<template>
    <div>
        <vort-spin :spinning="loading">
            <div class="space-y-4">
            <!-- Header -->
            <div class="bg-white rounded-xl p-6">
                <div class="flex items-center gap-3 mb-4">
                    <a class="text-gray-400 hover:text-gray-600 cursor-pointer" @click="goBack">
                        <ArrowLeft :size="18" />
                    </a>
                    <h3 class="text-lg font-medium text-gray-800">{{ project.name || '项目详情' }}</h3>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div v-if="project.product">
                        <span class="text-sm text-gray-400">产品</span>
                        <div class="text-sm text-gray-800 mt-1">{{ project.product }}</div>
                    </div>
                    <div v-if="project.iteration">
                        <span class="text-sm text-gray-400">迭代</span>
                        <div class="text-sm text-gray-800 mt-1">{{ project.iteration }}</div>
                    </div>
                    <div v-if="project.version">
                        <span class="text-sm text-gray-400">版本</span>
                        <div class="text-sm text-gray-800 mt-1">v{{ project.version }}</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">周期</span>
                        <div class="text-sm text-gray-800 mt-1">
                            {{ project.start_date ? project.start_date.split('T')[0] : '-' }}
                            ~
                            {{ project.end_date ? project.end_date.split('T')[0] : '未定' }}
                        </div>
                    </div>
                </div>
                <div v-if="project.description" class="mt-3">
                    <span class="text-sm text-gray-400">描述</span>
                    <div class="mt-1">
                        <MarkdownView :content="project.description" />
                    </div>
                </div>
            </div>

            <!-- Stats -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="bg-white rounded-xl p-5 flex items-center gap-4">
                    <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                        <ListChecks :size="18" class="text-blue-600" />
                    </div>
                    <div>
                        <div class="text-xl font-bold text-gray-800">{{ stats.stories.total }}</div>
                        <div class="text-xs text-gray-400">需求 · 已完成 {{ stats.stories.done }}</div>
                    </div>
                </div>
                <div class="bg-white rounded-xl p-5 flex items-center gap-4">
                    <div class="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                        <CheckSquare :size="18" class="text-green-600" />
                    </div>
                    <div>
                        <div class="text-xl font-bold text-gray-800">{{ stats.tasks.total }}</div>
                        <div class="text-xs text-gray-400">任务 · 已完成 {{ stats.tasks.done }}</div>
                    </div>
                </div>
                <div class="bg-white rounded-xl p-5 flex items-center gap-4">
                    <div class="w-10 h-10 rounded-lg bg-red-50 flex items-center justify-center">
                        <Bug :size="18" class="text-red-600" />
                    </div>
                    <div>
                        <div class="text-xl font-bold text-gray-800">{{ stats.bugs.total }}</div>
                        <div class="text-xs text-gray-400">缺陷 · 已关闭 {{ stats.bugs.closed }}</div>
                    </div>
                </div>
            </div>

            <!-- Members -->
            <div class="bg-white rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-base font-medium text-gray-800">
                        <Users :size="16" class="inline mr-1" /> 项目成员
                    </h3>
                    <vort-button size="small" @click="memberDialogVisible = true">
                        <Plus :size="12" class="mr-1" /> 添加成员
                    </vort-button>
                </div>
                <div v-if="members.length === 0" class="text-sm text-gray-400 py-4 text-center">暂无成员</div>
                <div v-else class="space-y-2">
                    <div v-for="m in members" :key="m.id" class="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm text-blue-600 font-medium">
                                {{ (m.member_id || '?').slice(0, 2).toUpperCase() }}
                            </div>
                            <div>
                                <span class="text-sm text-gray-800">{{ m.member_id }}</span>
                                <vort-tag size="small" class="ml-2" :color="m.role === 'owner' ? 'orange' : m.role === 'pm' ? 'blue' : 'default'">{{ m.role }}</vort-tag>
                            </div>
                        </div>
                        <vort-popconfirm title="确认移除该成员？" @confirm="handleRemoveMember(m.member_id)">
                            <a class="text-sm text-red-500 cursor-pointer"><Trash2 :size="14" /></a>
                        </vort-popconfirm>
                    </div>
                </div>
            </div>

            <!-- Linked Repos -->
            <div v-if="repos.length > 0" class="bg-white rounded-xl p-6">
                <h3 class="text-base font-medium text-gray-800 mb-4">
                    <FolderGit2 :size="16" class="inline mr-1" /> 代码仓库
                </h3>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    <div v-for="r in repos" :key="r.id" class="border border-gray-100 rounded-lg p-3 hover:shadow-sm transition-shadow">
                        <div class="flex items-start justify-between mb-1">
                            <h4 class="text-sm font-medium text-gray-800 truncate flex-1">{{ r.name }}</h4>
                            <vort-tag v-if="r.is_private" size="small" color="default">私有</vort-tag>
                        </div>
                        <p class="text-xs text-gray-400 truncate mb-2">{{ r.full_name }}</p>
                        <div class="flex items-center gap-2 flex-wrap">
                            <vort-tag v-if="r.language" size="small" color="processing">{{ r.language }}</vort-tag>
                            <vort-tag size="small" :color="repoTypeColorMap[r.repo_type] || 'default'">{{ repoTypeLabels[r.repo_type] || r.repo_type }}</vort-tag>
                            <span class="text-xs text-gray-400">{{ r.default_branch }}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- AI Coding Activity -->
            <div v-if="codeTasks.length > 0" class="bg-white rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-base font-medium text-gray-800">
                        <TerminalSquare :size="16" class="inline mr-1" /> AI 编码活动
                    </h3>
                    <router-link :to="{ name: 'vortgit-code-tasks' }" class="text-sm text-blue-600 hover:underline">
                        查看全部
                    </router-link>
                </div>
                <VortTimeline>
                    <VortTimelineItem v-for="ct in codeTasks" :key="ct.id" :color="codeTaskStatusColor(ct.status) === 'error' ? 'red' : codeTaskStatusColor(ct.status) === 'success' ? 'green' : 'blue'">
                        <div class="flex items-start justify-between">
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 flex-wrap">
                                    <span class="text-sm text-gray-800">{{ ct.member_id }}</span>
                                    <span class="text-xs text-gray-400">触发了编码任务</span>
                                    <vort-tag :color="codeTaskStatusColor(ct.status)" size="small">{{ codeTaskStatusLabel(ct.status) }}</vort-tag>
                                </div>
                                <div class="text-sm text-gray-600 mt-1 truncate">{{ ct.task_description }}</div>
                                <div class="flex items-center gap-3 mt-1 text-xs text-gray-400">
                                    <span>{{ repoNameById(ct.repo_id) }}</span>
                                    <span v-if="ct.files_changed?.length">{{ ct.files_changed.length }} 个文件</span>
                                    <span>{{ formatTime(ct.created_at) }}</span>
                                </div>
                            </div>
                            <a v-if="ct.pr_url" :href="ct.pr_url" target="_blank" class="text-blue-500 hover:text-blue-700 ml-2 shrink-0">
                                <ExternalLink :size="14" />
                            </a>
                        </div>
                    </VortTimelineItem>
                </VortTimeline>
            </div>

            <!-- Recent Stories -->
            <div class="bg-white rounded-xl p-6">
                <h3 class="text-base font-medium text-gray-800 mb-4">最近需求</h3>
                <div v-if="stories.length === 0" class="text-sm text-gray-400 py-4 text-center">暂无需求</div>
                <div v-else class="space-y-2">
                    <div v-for="s in stories" :key="s.id" class="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50">
                        <span class="text-sm text-gray-800 truncate flex-1">{{ s.title }}</span>
                        <vort-tag :color="stateColorMap[s.state] || 'default'" size="small">{{ stateLabel(s.state) }}</vort-tag>
                    </div>
                </div>
            </div>
            </div>
        </vort-spin>

        <!-- Add Member Dialog -->
        <vort-dialog :open="memberDialogVisible" title="添加项目成员" :width="400" @update:open="memberDialogVisible = $event">
            <vort-form ref="memberFormRef" :model="memberFormData" :rules="memberValidationSchema" label-width="60px">
                <vort-form-item label="成员ID" name="member_id" required has-feedback>
                    <vort-input v-model="newMemberId" placeholder="输入成员 ID" />
                </vort-form-item>
                <vort-form-item label="角色" name="role">
                    <vort-select v-model="newMemberRole" class="w-full">
                        <vort-select-option value="owner">Owner</vort-select-option>
                        <vort-select-option value="pm">PM</vort-select-option>
                        <vort-select-option value="dev">开发</vort-select-option>
                        <vort-select-option value="tester">测试</vort-select-option>
                        <vort-select-option value="member">成员</vort-select-option>
                        <vort-select-option value="viewer">观察者</vort-select-option>
                    </vort-select>
                </vort-form-item>
            </vort-form>
            <template #footer>
                <div class="flex justify-end gap-3">
                    <vort-button @click="memberDialogVisible = false">取消</vort-button>
                    <vort-button variant="primary" @click="handleAddMember">确定</vort-button>
                </div>
            </template>
        </vort-dialog>
    </div>
</template>

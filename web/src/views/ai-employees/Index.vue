<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
    getMembers, getMember, updateMember, deleteMember, startMemberChat,
    getVirtualRoles, createVirtualRole, updateVirtualRole, deleteVirtualRole,
    getWebhooks, getRemoteNodes, uploadMemberAvatar,
} from "@/api";
import { message } from "@/components/vort";
import { MemberWizard } from "@/components/vort-biz/member-wizard";
import AvatarCropper from "vue-avatar-cropper";
import "cropperjs/dist/cropper.min.css";
import {
    Plus, Settings, Bot, MessageSquare, Trash2,
    Webhook, Cpu, Unlink, Pencil, Users, BarChart3, MessageCircle, Clock,
    ChevronDown, ChevronUp,
} from "lucide-vue-next";

const router = useRouter();

// ---- Types ----

interface PostItem {
    id: string;
    key: string;
    name: string;
    description: string;
    icon: string;
    default_persona: string;
    default_auto_report: boolean;
    default_report_frequency: string;
    enabled: boolean;
}

interface AIEmployee {
    id: string;
    name: string;
    email: string;
    phone: string;
    position: string;
    status: string;
    is_account: boolean;
    is_virtual: boolean;
    virtual_role?: string;
    virtual_role_name?: string;
    post?: string;
    posts?: string[];
    has_password: boolean;
    roles: string[];
    platform_accounts: Record<string, string>;
    departments: string[];
    avatar_url?: string;
    bio?: string;
    auto_report?: boolean;
    report_frequency?: string;
    remote_node_id?: string;
    created_at: string;
}

interface EmployeeDetail extends AIEmployee {
    remote_node_id: string;
    identities: any[];
    departments: any[];
    permissions: string[];
}

interface RemoteNodeOption {
    id: string;
    name: string;
    node_type: string;
    gateway_url: string;
    status: string;
}

// ---- State: employee list ----

const employees = ref<AIEmployee[]>([]);
const loading = ref(false);
const posts = ref<PostItem[]>([]);
const activeCategory = ref("all");

const filteredEmployees = computed(() => {
    if (activeCategory.value === "all") return employees.value;
    return employees.value.filter(e => (e.post || e.virtual_role) === activeCategory.value);
});

const postCounts = computed(() => {
    const map: Record<string, number> = {};
    for (const e of employees.value) {
        const key = e.post || e.virtual_role || "";
        if (key) map[key] = (map[key] || 0) + 1;
    }
    return map;
});

// ---- State: stats ----

const stats = ref<Record<string, { total_sessions: number; today_sessions: number; last_active_at: string }>>({});

// ---- State: list-level webhooks (for card indicators) ----

const allWebhooks = ref<any[]>([]);

const webhooksByMember = computed(() => {
    const map: Record<string, any[]> = {};
    for (const wh of allWebhooks.value) {
        if (!wh.member_id) continue;
        (map[wh.member_id] ??= []).push(wh);
    }
    return map;
});

function getNodeInfo(nodeId: string | undefined): RemoteNodeOption | undefined {
    if (!nodeId) return undefined;
    return remoteNodes.value.find(n => n.id === nodeId);
}

// ---- State: detail drawer ----

const detailOpen = ref(false);
const detailLoading = ref(false);
const currentEmployee = ref<EmployeeDetail | null>(null);
const editForm = ref({ name: "", email: "", phone: "", bio: "", virtual_role: "", posts: [] as string[] });
const savingEdit = ref(false);
const showAvatarCropper = ref(false);
const uploadingAvatar = ref(false);
const memberWebhooks = ref<any[]>([]);
const remoteNodes = ref<RemoteNodeOption[]>([]);
const savingNodeBinding = ref(false);

// ---- State: post management dialog ----

const postDialogOpen = ref(false);
const postList = ref<PostItem[]>([]);
const postLoading = ref(false);
const postEditing = ref<Partial<PostItem> | null>(null);
const postEditMode = ref<"add" | "edit">("add");
const postSubmitting = ref(false);

// ---- State: create wizard ----

const wizardOpen = ref(false);

// ---- State: category tabs ----

const isExpanded = ref(false);
const tabContainerRef = ref<HTMLElement | null>(null);
const showMoreButton = ref(false);

const updateShowMore = () => {
    if (!tabContainerRef.value) return;
    // Check if content overflows
    showMoreButton.value = tabContainerRef.value.scrollHeight > tabContainerRef.value.clientHeight + 5; // +5 for tolerance
};

// Re-check on window resize or posts change
onMounted(() => {
    window.addEventListener("resize", updateShowMore);
});

// Watch posts to update overflow check
import { watch, nextTick } from "vue";
watch(posts, () => {
    nextTick(updateShowMore);
});

const toggleExpand = () => {
    isExpanded.value = !isExpanded.value;
};

const postColors: Record<string, string> = {};
const colorPalette = [
    "bg-blue-100 text-blue-700",
    "bg-emerald-100 text-emerald-700",
    "bg-violet-100 text-violet-700",
    "bg-amber-100 text-amber-700",
    "bg-rose-100 text-rose-700",
    "bg-cyan-100 text-cyan-700",
    "bg-fuchsia-100 text-fuchsia-700",
    "bg-lime-100 text-lime-700",
];

function getPostColor(postKey: string): string {
    if (!postColors[postKey]) {
        const idx = Object.keys(postColors).length % colorPalette.length;
        postColors[postKey] = colorPalette[idx];
    }
    return postColors[postKey];
}

function getPostName(postKey: string): string {
    const p = posts.value.find(p => p.key === postKey);
    return p?.name || postKey || "未分配岗位";
}

function getEmployeePosts(employee: Pick<AIEmployee, "posts" | "post" | "virtual_role">): string[] {
    const raw = employee.posts?.length ? employee.posts : [employee.post || employee.virtual_role || ""];
    return Array.from(new Set(raw.map(item => (item || "").trim()).filter(Boolean)));
}

// ---- Load data ----

async function loadEmployees() {
    loading.value = true;
    try {
        const res: any = await getMembers({ is_virtual: true, size: 200 });
        employees.value = res?.members || [];
    } catch { message.error("加载 AI 员工列表失败"); }
    finally { loading.value = false; }
}

async function loadPosts() {
    try {
        const res: any = await getVirtualRoles();
        posts.value = (res.posts || []).filter((p: PostItem) => p.enabled);
    } catch { /* ignore */ }
}

async function loadStats() {
    try {
        const { getVirtualMemberStats } = await import("@/api");
        const res: any = await getVirtualMemberStats();
        if (res?.stats) {
            const map: Record<string, any> = {};
            for (const s of res.stats) {
                map[s.member_id] = s;
            }
            stats.value = map;
        }
    } catch { /* stats API may not exist yet */ }
}

// ---- Computed stats ----

const totalEmployees = computed(() => employees.value.length);
const todayActiveCount = computed(() => {
    const today = new Date().toISOString().slice(0, 10);
    return Object.values(stats.value).filter(s => s.last_active_at?.startsWith(today)).length;
});
const todayTotalSessions = computed(() => {
    return Object.values(stats.value).reduce((sum, s) => sum + (s.today_sessions || 0), 0);
});

function getEmployeeStat(memberId: string) {
    return stats.value[memberId];
}

function formatLastActive(dateStr: string): string {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "刚刚";
    if (diffMin < 60) return `${diffMin}分钟前`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}小时前`;
    const diffDay = Math.floor(diffHour / 24);
    if (diffDay < 30) return `${diffDay}天前`;
    return d.toLocaleDateString("zh-CN");
}

// ---- Detail drawer ----

async function openDetail(emp: AIEmployee) {
    detailOpen.value = true;
    detailLoading.value = true;
    memberWebhooks.value = [];
    try {
        const res: any = await getMember(emp.id);
        currentEmployee.value = res;
        editForm.value = {
            name: res.name || "",
            email: res.email || "",
            phone: res.phone || "",
            bio: res.bio || "",
            virtual_role: res.post || res.virtual_role || emp.post || emp.virtual_role || "",
            posts: getEmployeePosts(res),
        };
        try {
            const whRes: any = await getWebhooks();
            const all = Array.isArray(whRes) ? whRes : [];
            memberWebhooks.value = all.filter((w: any) => w.member_id === emp.id);
        } catch { /* ignore */ }
    } catch { message.error("加载详情失败"); }
    finally { detailLoading.value = false; }
}

async function handleSaveEdit() {
    if (!currentEmployee.value) return;
    savingEdit.value = true;
    try {
        const normalizedPosts = Array.from(new Set(editForm.value.posts.map(item => item.trim()).filter(Boolean)));
        const res: any = await updateMember(currentEmployee.value.id, {
            ...editForm.value,
            posts: normalizedPosts,
            virtual_role: normalizedPosts[0] || "",
        });
        if (res?.success) {
            message.success("保存成功");
            await loadEmployees();
            await openDetail(currentEmployee.value);
        } else { message.error(res?.error || "保存失败"); }
    } catch { message.error("保存失败"); }
    finally { savingEdit.value = false; }
}

async function handleAvatarUpload(cropper: any) {
    if (!currentEmployee.value) return;
    const canvas = cropper.getCroppedCanvas({ width: 512, height: 512 });
    if (!canvas) return;

    uploadingAvatar.value = true;
    try {
        const blob: Blob = await new Promise((resolve) =>
            canvas.toBlob((b: Blob) => resolve(b), "image/png", 0.9)
        );
        const file = new File([blob], "avatar.png", { type: "image/png" });
        const res: any = await uploadMemberAvatar(currentEmployee.value.id, file);
        if (res?.success && res.avatar_url) {
            message.success("头像已更新");
            await loadEmployees();
            await openDetail(currentEmployee.value);
        } else {
            message.error(res?.error || "上传失败");
        }
    } catch {
        message.error("上传失败");
    } finally {
        uploadingAvatar.value = false;
    }
}

async function handleDeleteEmployee(emp: EmployeeDetail) {
    try {
        await deleteMember(emp.id);
        message.success("已删除");
        detailOpen.value = false;
        await loadEmployees();
    } catch { message.error("删除失败"); }
}

async function handleBindRemoteNode(memberId: string, nodeId: string) {
    savingNodeBinding.value = true;
    try {
        const res: any = await updateMember(memberId, { remote_node_id: nodeId } as any);
        if (res?.success) {
            message.success(nodeId ? "节点已绑定" : "已解除绑定");
            if (currentEmployee.value) await openDetail(currentEmployee.value);
        } else { message.error("绑定失败"); }
    } catch { message.error("绑定失败"); }
    finally { savingNodeBinding.value = false; }
}

async function handleChat(emp: AIEmployee) {
    try {
        const res: any = await startMemberChat(emp.id);
        if (res?.session_id) {
            router.push({ name: "chat", query: { session: res.session_id, contact: emp.id, type: "member" } });
        }
    } catch { message.error("进入对话失败"); }
}

// ---- Post management ----

async function openPostDialog() {
    postDialogOpen.value = true;
    postEditing.value = null;
    await loadPostList();
}

async function loadPostList() {
    postLoading.value = true;
    try {
        const res: any = await getVirtualRoles();
        postList.value = res.posts || [];
    } catch { message.error("加载岗位列表失败"); }
    finally { postLoading.value = false; }
}

function startAddPost() {
    postEditMode.value = "add";
    postEditing.value = {
        key: "", name: "", description: "", icon: "Bot",
        default_persona: "", default_auto_report: false, default_report_frequency: "daily", enabled: true,
    };
}

function startEditPost(post: PostItem) {
    postEditMode.value = "edit";
    postEditing.value = { ...post };
}

function cancelPostEdit() {
    postEditing.value = null;
}

async function handleSavePost() {
    if (!postEditing.value?.key?.trim() || !postEditing.value?.name?.trim()) {
        message.warning("请填写岗位标识和名称");
        return;
    }
    postSubmitting.value = true;
    try {
        if (postEditMode.value === "add") {
            await createVirtualRole({
                key: postEditing.value.key!,
                name: postEditing.value.name!,
                description: postEditing.value.description || "",
                icon: postEditing.value.icon || "Bot",
                default_persona: postEditing.value.default_persona || "",
                default_auto_report: postEditing.value.default_auto_report || false,
                default_report_frequency: postEditing.value.default_report_frequency || "daily",
            });
            message.success("岗位已创建");
        } else {
            await updateVirtualRole(postEditing.value.id!, {
                name: postEditing.value.name,
                description: postEditing.value.description,
                icon: postEditing.value.icon,
                default_persona: postEditing.value.default_persona,
                default_auto_report: postEditing.value.default_auto_report,
                default_report_frequency: postEditing.value.default_report_frequency,
            });
            message.success("岗位已更新");
        }
        postEditing.value = null;
        await Promise.all([loadPostList(), loadPosts()]);
    } catch (e: any) { message.error(e.message || "操作失败"); }
    finally { postSubmitting.value = false; }
}

async function handleDeletePost(post: PostItem) {
    try {
        await deleteVirtualRole(post.id);
        message.success("已删除");
        await Promise.all([loadPostList(), loadPosts()]);
    } catch (e: any) { message.error(e.message || "删除失败"); }
}

async function handleTogglePost(post: PostItem) {
    try {
        await updateVirtualRole(post.id, { enabled: !post.enabled });
        message.success(post.enabled ? "已禁用" : "已启用");
        await Promise.all([loadPostList(), loadPosts()]);
    } catch (e: any) { message.error(e.message || "操作失败"); }
}

// ---- Create wizard ----

async function handleWizardComplete() {
    await Promise.all([loadEmployees(), loadStats()]);
}

// ---- Init ----

onMounted(async () => {
    await loadPosts();
    await loadEmployees();
    loadStats();
    loadRemoteNodes();
    loadAllWebhooks();
});

async function loadAllWebhooks() {
    try {
        const res: any = await getWebhooks();
        allWebhooks.value = Array.isArray(res) ? res : [];
    } catch { /* ignore */ }
}

async function loadRemoteNodes() {
    try {
        const res: any = await getRemoteNodes();
        remoteNodes.value = (res?.nodes || []).map((n: any) => ({
            id: n.id, name: n.name, node_type: n.node_type || "openclaw", gateway_url: n.gateway_url, status: n.status,
        }));
    } catch { /* ignore */ }
}
</script>

<template>
    <div class="space-y-5">
        <!-- Stats overview -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div class="bg-white rounded-xl px-5 py-4 border border-gray-100">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center">
                        <Users :size="18" class="text-blue-600" />
                    </div>
                    <div>
                        <div class="text-2xl font-semibold text-gray-800">{{ totalEmployees }}</div>
                        <div class="text-xs text-gray-400">AI 员工总数</div>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-xl px-5 py-4 border border-gray-100">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center">
                        <MessageCircle :size="18" class="text-emerald-600" />
                    </div>
                    <div>
                        <div class="text-2xl font-semibold text-gray-800">{{ todayTotalSessions }}</div>
                        <div class="text-xs text-gray-400">今日对话数</div>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-xl px-5 py-4 border border-gray-100">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                        <BarChart3 :size="18" class="text-amber-600" />
                    </div>
                    <div>
                        <div class="text-2xl font-semibold text-gray-800">{{ todayActiveCount }}</div>
                        <div class="text-xs text-gray-400">今日活跃</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Header + category tabs -->
        <div class="mb-4">
            <div class="flex items-center justify-between mb-4">
                <div>
                    <h2 class="text-lg font-medium text-gray-800">AI 员工</h2>
                    <p class="text-sm text-gray-500 mt-1">管理团队的 AI 员工，配置岗位和工作方式</p>
                </div>
                <div class="flex items-center gap-2">
                    <VortButton @click="openPostDialog" class="bg-white border-gray-200">
                        <Settings :size="14" class="mr-1" /> 管理岗位
                    </VortButton>
                    <VortButton variant="primary" @click="wizardOpen = true">
                        <Plus :size="14" class="mr-1" /> 创建 AI 员工
                    </VortButton>
                </div>
            </div>

            <!-- Category tabs -->
            <div class="relative">
                <div
                    ref="tabContainerRef"
                    class="flex flex-wrap gap-2 overflow-hidden transition-all duration-300 pr-24"
                    :class="isExpanded ? 'h-auto' : 'h-[36px]'"
                >
                    <button
                        class="flex-shrink-0 px-4 py-1.5 text-sm rounded-lg transition-colors whitespace-nowrap border h-[34px]"
                        :class="activeCategory === 'all'
                            ? 'bg-blue-600 text-white border-blue-600 font-medium'
                            : 'bg-white text-gray-600 border-transparent hover:bg-gray-50'"
                        @click="activeCategory = 'all'"
                    >
                        全部
                        <span
                            class="ml-1 text-xs px-1.5 py-0.5 rounded-full"
                            :class="activeCategory === 'all' ? 'bg-blue-500/30 text-white' : 'bg-gray-100 text-gray-500'"
                        >{{ employees.length }}</span>
                    </button>
                    <button
                        v-for="post in posts"
                        :key="post.key"
                        class="flex-shrink-0 px-4 py-1.5 text-sm rounded-lg transition-colors whitespace-nowrap border h-[34px]"
                        :class="activeCategory === post.key
                            ? 'bg-blue-600 text-white border-blue-600 font-medium'
                            : 'bg-white text-gray-600 border-transparent hover:bg-gray-50'"
                        @click="activeCategory = post.key"
                    >
                        {{ post.name }}
                        <span
                            v-if="postCounts[post.key]"
                            class="ml-1 text-xs px-1.5 py-0.5 rounded-full"
                            :class="activeCategory === post.key ? 'bg-blue-500/30 text-white' : 'bg-gray-100 text-gray-500'"
                        >{{ postCounts[post.key] }}</span>
                    </button>
                </div>

                <!-- More button (absolute) -->
                <div
                    v-if="showMoreButton || isExpanded"
                    class="absolute right-0 top-0 h-[36px] flex items-center bg-gradient-to-l from-gray-50 from-80% to-transparent pl-6"
                >
                    <button
                        class="text-sm text-gray-500 hover:text-gray-800 flex items-center bg-transparent px-2"
                        @click="toggleExpand"
                    >
                        {{ isExpanded ? '收起筛选' : '更多筛选' }}
                        <component :is="isExpanded ? 'ChevronUp' : 'ChevronDown'" :size="14" class="ml-1" />
                    </button>
                </div>
            </div>
        </div>

        <!-- Card grid -->
        <VortSpin :spinning="loading">
            <div v-if="filteredEmployees.length" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                <div
                    v-for="emp in filteredEmployees"
                    :key="emp.id"
                    class="bg-white rounded-xl border border-gray-100 p-4 hover:shadow-md hover:border-gray-200 transition-all cursor-pointer group"
                    @click="openDetail(emp)"
                >
                    <!-- Top: avatar + name -->
                    <div class="flex items-start gap-3">
                        <div
                            class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-sm font-medium"
                            :class="getPostColor(emp.post || emp.virtual_role || '')"
                        >
                            <img
                                v-if="emp.avatar_url"
                                :src="emp.avatar_url"
                                class="w-10 h-10 rounded-lg object-cover"
                            />
                            <Bot v-else :size="20" />
                        </div>
                        <div class="min-w-0 flex-1">
                            <div class="font-medium text-gray-800 truncate">{{ emp.name }}</div>
                            <div class="flex flex-wrap gap-1 mt-1">
                                <VortTag
                                    v-for="postKey in getEmployeePosts(emp).slice(0, 2)"
                                    :key="postKey"
                                    size="small"
                                    color="blue"
                                    :bordered="false"
                                >
                                    {{ getPostName(postKey) }}
                                </VortTag>
                                <VortTag v-if="getEmployeePosts(emp).length > 2" size="small" color="blue" :bordered="false">
                                    +{{ getEmployeePosts(emp).length - 2 }}
                                </VortTag>
                            </div>
                        </div>
                    </div>

                    <!-- Description -->
                    <div class="text-xs text-gray-500 mt-3 line-clamp-2 min-h-[32px]">
                        {{ emp.bio || '暂无描述' }}
                    </div>

                    <!-- Bottom: stats + indicators + action -->
                    <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-50">
                        <div class="flex items-center gap-2">
                            <div class="text-xs text-gray-400">
                                <template v-if="getEmployeeStat(emp.id)?.today_sessions">
                                    <MessageCircle :size="12" class="inline mr-0.5 -mt-px" />
                                    今日 {{ getEmployeeStat(emp.id).today_sessions }} 次对话
                                </template>
                                <template v-else-if="getEmployeeStat(emp.id)?.last_active_at">
                                    <Clock :size="12" class="inline mr-0.5 -mt-px" />
                                    {{ formatLastActive(getEmployeeStat(emp.id).last_active_at) }}
                                </template>
                                <template v-else>
                                    <Clock :size="12" class="inline mr-0.5 -mt-px" />
                                    暂无活动
                                </template>
                            </div>
                            <div class="flex items-center gap-1.5">
                                <span
                                    v-if="webhooksByMember[emp.id]?.length"
                                    class="flex items-center text-indigo-400"
                                    :title="`${webhooksByMember[emp.id].length} 个外部连接`"
                                >
                                    <Webhook :size="12" />
                                </span>
                                <vort-tip
                                    v-if="emp.remote_node_id && getNodeInfo(emp.remote_node_id)"
                                    :title="`工作节点: ${getNodeInfo(emp.remote_node_id)?.name || ''}`"
                                >
                                    <span
                                        class="flex items-center"
                                        :class="['online', 'running'].includes(getNodeInfo(emp.remote_node_id)?.status || '') ? 'text-emerald-500' : 'text-red-400'"
                                    >
                                        <Cpu :size="12" />
                                    </span>
                                </vort-tip>
                            </div>
                        </div>
                        <VortButton
                            size="small"
                            class="opacity-0 group-hover:opacity-100 transition-opacity"
                            @click.stop="handleChat(emp)"
                        >
                            <MessageSquare :size="12" class="mr-1" /> 对话
                        </VortButton>
                    </div>
                </div>
            </div>

            <!-- Empty state -->
            <div v-else-if="!loading" class="bg-white rounded-xl border border-gray-100 py-16 text-center">
                <Bot :size="48" class="mx-auto text-gray-300 mb-4" />
                <div class="text-gray-500 mb-2">{{ activeCategory === 'all' ? '暂无 AI 员工' : '该岗位下暂无 AI 员工' }}</div>
                <VortButton variant="primary" size="small" @click="wizardOpen = true">
                    <Plus :size="14" class="mr-1" /> 创建第一个 AI 员工
                </VortButton>
            </div>
        </VortSpin>

        <!-- Detail drawer -->
        <VortDrawer v-model:open="detailOpen" :title="currentEmployee?.name || 'AI 员工详情'" :width="560">
            <VortSpin :spinning="detailLoading">
                <div v-if="currentEmployee" class="space-y-5">
                    <!-- Basic info -->
                    <div class="rounded-lg border border-gray-100 bg-white">
                        <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50/60 rounded-t-lg">
                            <Bot :size="15" class="text-gray-400" />
                            <h4 class="text-sm font-semibold text-gray-700">基本信息</h4>
                        </div>
                        <div class="px-4 py-3">
                            <div class="flex items-center gap-4 pb-4 mb-4 border-b border-gray-100">
                                <div class="w-16 h-16 rounded-xl bg-blue-50 flex items-center justify-center overflow-hidden flex-shrink-0">
                                    <img v-if="currentEmployee.avatar_url" :src="currentEmployee.avatar_url" class="w-full h-full object-cover" />
                                    <span v-else class="text-xl font-medium text-blue-600">{{ (editForm.name || currentEmployee.name || "?")[0] }}</span>
                                </div>
                                <div class="min-w-0 flex-1">
                                    <div class="text-sm font-medium text-gray-800">员工头像</div>
                                    <div class="text-xs text-gray-400 mt-1">支持 jpg/png/gif/webp，上传后会同步用于聊天和列表展示</div>
                                </div>
                                <VortButton size="small" :loading="uploadingAvatar" @click="showAvatarCropper = true">
                                    更换头像
                                </VortButton>
                                <avatar-cropper
                                    v-model="showAvatarCropper"
                                    :upload-handler="handleAvatarUpload"
                                    :cropper-options="{ aspectRatio: 1, autoCropArea: 1, viewMode: 1, movable: true, zoomable: true }"
                                    :output-options="{ width: 512, height: 512 }"
                                    output-mime="image/png"
                                />
                            </div>
                            <VortForm label-width="70px" size="small">
                                <VortFormItem label="姓名">
                                    <VortInput v-model="editForm.name" />
                                </VortFormItem>
                                <VortFormItem label="邮箱">
                                    <VortInput v-model="editForm.email" placeholder="请输入邮箱" />
                                </VortFormItem>
                                <VortFormItem label="手机">
                                    <VortInput v-model="editForm.phone" placeholder="请输入手机号" />
                                </VortFormItem>
                                <VortFormItem label="岗位">
                                    <VortSelect
                                        v-model="editForm.posts"
                                        mode="multiple"
                                        placeholder="请选择一个或多个岗位"
                                        allow-clear
                                        :max-tag-count="3"
                                        style="width: 100%"
                                    >
                                        <VortSelectOption v-for="post in posts" :key="post.key" :value="post.key">
                                            {{ post.name }}
                                        </VortSelectOption>
                                    </VortSelect>
                                </VortFormItem>
                                <VortFormItem label="描述">
                                    <VortTextarea v-model="editForm.bio" placeholder="AI 员工的个人简介" :rows="3" />
                                </VortFormItem>
                                <VortFormItem>
                                    <VortButton variant="primary" size="small" :loading="savingEdit" @click="handleSaveEdit">
                                        保存
                                    </VortButton>
                                </VortFormItem>
                            </VortForm>
                        </div>
                    </div>

                    <!-- Webhooks -->
                    <div class="rounded-lg border border-gray-100 bg-white">
                        <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50/60 rounded-t-lg">
                            <Webhook :size="15" class="text-gray-400" />
                            <h4 class="text-sm font-semibold text-gray-700">外部连接（Inbound）</h4>
                        </div>
                        <div class="px-4 py-3">
                            <div class="text-xs text-gray-400 mb-3">
                                接收外部系统（GitHub、GitLab、OpenClaw 等）推送的事件，AI 员工可自动响应代码提交、Issue、IM 消息等并执行处理。
                            </div>
                            <div v-if="memberWebhooks.length" class="space-y-2">
                                <div
                                    v-for="wh in memberWebhooks" :key="wh.name"
                                    class="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-100"
                                >
                                    <div class="flex items-center gap-2">
                                        <Webhook :size="14" class="text-indigo-500" />
                                        <span class="text-sm font-medium">{{ wh.name }}</span>
                                        <VortTag size="small" :color="wh.action_type === 'openclaw_bridge' ? 'purple' : 'blue'">
                                            {{ wh.action_type === 'openclaw_bridge' ? 'OpenClaw' : 'Webhook' }}
                                        </VortTag>
                                    </div>
                                    <code class="text-xs text-gray-400">POST /api/webhooks/{{ wh.name }}</code>
                                </div>
                            </div>
                            <div v-else class="text-sm text-gray-400 flex items-center gap-2 py-0.5">
                                <Unlink :size="14" /> 暂无外部连接
                                <router-link to="/webhooks" class="text-blue-600 hover:underline ml-1">前往配置</router-link>
                            </div>
                        </div>
                    </div>

                    <!-- Remote work node -->
                    <div class="rounded-lg border border-gray-100 bg-white">
                        <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50/60 rounded-t-lg">
                            <Cpu :size="15" class="text-gray-400" />
                            <h4 class="text-sm font-semibold text-gray-700">工作节点（Outbound）</h4>
                        </div>
                        <div class="px-4 py-3">
                            <div class="text-xs text-gray-400 mb-3">
                                绑定远程节点后，AI 员工可在远程电脑上执行编码、运行命令、操作文件等实际工作任务，相当于为 AI 员工配备了一台"工作电脑"。
                            </div>
                            <VortSpin :spinning="savingNodeBinding">
                                <VortSelect
                                    :model-value="currentEmployee.remote_node_id || ''"
                                    placeholder="未绑定（选择节点后可远程执行任务）"
                                    allow-clear
                                    style="width: 100%"
                                    @update:model-value="(val: string) => handleBindRemoteNode(currentEmployee!.id, val || '')"
                                >
                                    <VortSelectOption v-for="node in remoteNodes" :key="node.id" :value="node.id">
                                        <div class="flex items-center gap-2">
                                            <span
                                                class="w-2 h-2 rounded-full flex-shrink-0"
                                                :class="['online', 'running'].includes(node.status) ? 'bg-green-500' : ['offline', 'stopped', 'error'].includes(node.status) ? 'bg-red-400' : 'bg-gray-300'"
                                            />
                                            <span>{{ node.name }}</span>
                                            <span class="text-xs px-1 py-0.5 rounded" :class="node.node_type === 'docker' ? 'bg-purple-50 text-purple-600' : 'bg-blue-50 text-blue-600'">
                                                {{ node.node_type === 'docker' ? 'Docker' : 'OpenClaw' }}
                                            </span>
                                            <span class="text-xs text-gray-400">{{ node.node_type === 'docker' ? (['running', 'stopped'].includes(node.status) ? (node.status === 'running' ? '运行中' : '已停止') : node.status) : node.gateway_url }}</span>
                                        </div>
                                    </VortSelectOption>
                                </VortSelect>
                                <div class="mt-2 text-xs text-gray-400">
                                    <router-link to="/remote-nodes" class="text-blue-600 hover:underline">管理节点</router-link>
                                </div>
                            </VortSpin>
                        </div>
                    </div>

                    <!-- Actions -->
                    <div class="flex items-center gap-3 pt-2">
                        <VortButton variant="primary" @click="handleChat(currentEmployee)">
                            <MessageSquare :size="14" class="mr-1" /> 发起对话
                        </VortButton>
                        <VortPopconfirm title="确认删除该 AI 员工？删除后不可恢复。" @confirm="handleDeleteEmployee(currentEmployee)">
                            <VortButton variant="danger">
                                <Trash2 :size="14" class="mr-1" /> 删除
                            </VortButton>
                        </VortPopconfirm>
                    </div>
                </div>
            </VortSpin>
        </VortDrawer>

        <!-- Post management dialog -->
        <VortDrawer v-model:open="postDialogOpen" title="岗位管理" :width="560">
            <div class="space-y-4">
                <div class="flex items-center justify-between">
                    <p class="text-sm text-gray-500">管理 AI 员工的岗位模板</p>
                    <VortButton size="small" @click="startAddPost">
                        <Plus :size="14" class="mr-1" /> 新增岗位
                    </VortButton>
                </div>

                <!-- Post edit form -->
                <div v-if="postEditing" class="rounded-lg border border-blue-200 bg-blue-50/30 p-4 space-y-3">
                    <div class="text-sm font-medium text-gray-700">
                        {{ postEditMode === 'add' ? '新增岗位' : '编辑岗位' }}
                    </div>
                    <VortForm label-width="80px" size="small">
                        <VortFormItem label="标识" required>
                            <VortInput
                                v-model="postEditing.key"
                                placeholder="如 developer, pm"
                                :disabled="postEditMode === 'edit'"
                            />
                        </VortFormItem>
                        <VortFormItem label="名称" required>
                            <VortInput v-model="postEditing.name" placeholder="如 开发工程师" />
                        </VortFormItem>
                        <VortFormItem label="描述">
                            <VortInput v-model="postEditing.description" placeholder="一句话描述岗位职责" />
                        </VortFormItem>
                        <VortFormItem label="默认人设">
                            <VortTextarea
                                v-model="postEditing.default_persona"
                                placeholder="设置 AI 员工的默认人设描述"
                                :rows="2"
                            />
                        </VortFormItem>
                        <VortFormItem label="自动汇报">
                            <div class="flex items-center gap-2">
                                <VortSwitch v-model:checked="postEditing.default_auto_report" />
                                <span class="text-sm text-gray-600">启用后自动生成汇报</span>
                            </div>
                        </VortFormItem>
                    </VortForm>

                    <div class="flex justify-end gap-2 pt-2">
                        <VortButton size="small" @click="cancelPostEdit">取消</VortButton>
                        <VortButton variant="primary" size="small" :loading="postSubmitting" @click="handleSavePost">
                            保存
                        </VortButton>
                    </div>
                </div>

                <!-- Post list -->
                <VortSpin :spinning="postLoading">
                    <div class="space-y-2">
                        <div
                            v-for="post in postList"
                            :key="post.id"
                            class="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
                        >
                            <div class="min-w-0 flex-1">
                                <div class="flex items-center gap-2">
                                    <span class="font-medium text-sm text-gray-800">{{ post.name }}</span>
                                    <code class="text-xs text-gray-400">{{ post.key }}</code>
                                    <VortTag v-if="!post.enabled" size="small" color="default">已禁用</VortTag>
                                </div>
                                <div v-if="post.description" class="text-xs text-gray-500 mt-0.5 truncate">
                                    {{ post.description }}
                                </div>
                            </div>
                            <div class="flex items-center gap-1 flex-shrink-0 ml-3">
                                <VortButton size="small" @click="startEditPost(post)">
                                    <Pencil :size="12" />
                                </VortButton>
                                <VortButton size="small" @click="handleTogglePost(post)">
                                    {{ post.enabled ? '禁用' : '启用' }}
                                </VortButton>
                                <VortPopconfirm title="确认删除该岗位？" @confirm="handleDeletePost(post)">
                                    <VortButton size="small" variant="danger">
                                        <Trash2 :size="12" />
                                    </VortButton>
                                </VortPopconfirm>
                            </div>
                        </div>
                        <div v-if="!postList.length && !postLoading" class="text-center py-8 text-sm text-gray-400">
                            暂无岗位，点击上方按钮创建
                        </div>
                    </div>
                </VortSpin>
            </div>
        </VortDrawer>

        <!-- Create wizard -->
        <MemberWizard
            :open="wizardOpen"
            default-member-type="virtual"
            @update:open="wizardOpen = $event"
            @complete="handleWizardComplete"
        />
    </div>
</template>

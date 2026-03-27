<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
    batchDeleteMembers, batchEnableAccount, batchDisableAccount,
    batchAssignRole, batchRemoveRole, batchAssignDept, batchRemoveDept,
} from "@/api";
import {
    RefreshCw, Search, Shield, UserCheck, UserX, Key,
    AlertTriangle, Check, X, Link, Lock, Trash2,
    ChevronDown, FolderTree, Plus, Pencil, UserPlus,
    Download, Calendar, CloudDownload, User, IdCard,
} from "lucide-vue-next";
import { message, dialog } from "@openvort/vort-ui";
import { DeptTree } from "@/components/vort-biz/dept-tree";
import { MemberWizard } from "@/components/vort-biz/member-wizard";
import { useContactMembers } from "./composables/useContactMembers";
import { useContactRoles } from "./composables/useContactRoles";
import { useContactDepartments } from "./composables/useContactDepartments";
import { useOrgCalendar } from "./composables/useOrgCalendar";

// ---- Shared state ----

const activeTab = ref("org");
const selectedDeptId = ref<number | null>(null);

// ---- Composables ----

const {
    members, membersTotal, membersPage, membersSize,
    searchText, filterRole, loadingMembers, loadingSync, loadingDedup,
    selectedIds, rowSelection,
    channels,
    suggestions, showSuggestions,
    drawerOpen, drawerLoading, currentMember, editForm, savingEdit,
    createMemberDialogOpen, createMemberForm, savingCreateMember, wizardOpen,
    roleDialogOpen, roleDialogMember, roleDialogLoading,
    generatedPassword, showGeneratedPassword, closeGeneratedPassword,
    loadMembers, handleSearch, handleSync, loadChannels, handleDedup,
    loadSuggestions, handleAccept, handleReject,
    openMemberDrawer, handleSaveEdit, handleToggleAccount, handleResetPassword,
    handleCreateMember, openCreateMemberDialog,
    handleDelete,
    openRoleDialog,
} = useContactMembers({
    selectedDeptId,
    refreshDeptTree: async () => { await loadDeptTree(); },
});

const {
    roles, allPermissions, selectedRoleIndex, selectedRole,
    roleMembers, loadingRoles, loadingRoleMembers,
    editingPerms, savingPermsInline, canEditPermissions, activePermCodes, hasPermChanges,
    groupedPermissions,
    roleEditDialogOpen, roleEditMode, roleEditForm, roleEditIsBuiltin, savingRole,
    isPermSelected, isGroupAllSelected, isGroupPartial, isSectionAllSelected, isSectionPartial,
    toggleSection, toggleGroup, togglePerm,
    savePermissionsInline, cancelPermEdit,
    openCreateRoleDialog, openEditRoleDialog, handleSaveRole, handleDeleteRole,
    togglePermission, isDialogGroupAllSelected, isDialogGroupPartial, toggleDialogGroup,
    isDialogSectionAllSelected, isDialogSectionPartial, toggleDialogSection,
    loadRoles, loadPermissions, loadRoleMembers,
    handleAssignRole, handleRemoveRole,
} = useContactRoles({
    loadMembers,
    openMemberDrawer,
    currentMember,
});

const {
    deptTree, expandedDeptIds, selectedDept, deptBreadcrumb,
    loadingDepts,
    deptDialogOpen, deptDialogMode, deptDialogForm, savingDept,
    addMemberDialogOpen, addMemberSearch, addMemberResults, addMemberLoading,
    drawerDeptDialogOpen,
    loadDeptTree, handleSelectDept, handleToggleDeptExpand,
    openCreateDeptDialog, openEditDeptDialog, handleSaveDept, handleDeleteDept,
    handleSearchAddMember, handleAddMemberToDept, handleRemoveMemberFromDept,
    handleAddDeptToMember, handleRemoveDeptFromMember,
} = useContactDepartments({
    selectedDeptId,
    loadMembers,
    membersPage,
    openMemberDrawer,
    currentMember,
});

const {
    calendarEntries, loadingCalendar, calendarYear, syncingHolidays,
    workSettings, editingWorkSettings, savingWorkSettings, workSettingsForm,
    calendarDialogOpen, calendarForm, savingCalendar,
    weekDayOptions, dayTypeOptions, dayTypeLabel, dayTypeColor,
    loadCalendar, loadWorkSettings,
    startEditWorkSettings, cancelEditWorkSettings, handleSaveWorkSettings,
    handleSyncHolidays,
    openCalendarDialog, handleSaveCalendar, handleDeleteCalendar,
} = useOrgCalendar();

// ---- Role dialog toggle (bridges members + roles composables) ----

async function handleRoleDialogToggle(roleName: string) {
    if (!roleDialogMember.value) return;
    const member = roleDialogMember.value;
    if (member.roles.length === 1 && member.roles[0] === roleName) return;
    roleDialogLoading.value = true;
    await handleAssignRole(member.id, roleName);
    const updated = members.value.find(m => m.id === member.id);
    if (updated) roleDialogMember.value = updated;
    roleDialogLoading.value = false;
    roleDialogOpen.value = false;
}

// ---- Batch operations ----

const batchRoleDialogOpen = ref(false);
const batchRoleAction = ref<"assign" | "remove">("assign");
const batchDeptDialogOpen = ref(false);
const batchDeptAction = ref<"assign" | "remove">("assign");

async function handleBatchDelete() {
    if (!selectedIds.value.length) return;
    dialog.confirm({
        title: `确定删除选中的 ${selectedIds.value.length} 个成员？此操作不可恢复。`,
        okType: "danger",
        onOk: async () => {
            const res: any = await batchDeleteMembers(selectedIds.value);
            if (res?.success) {
                message.success(`已删除 ${res.deleted} 个成员`);
                selectedIds.value = [];
                await loadMembers();
            } else {
                message.error("批量删除失败");
                throw new Error("批量删除失败");
            }
        },
    });
}

const batchPasswords = ref<{ id: string; name: string; password: string }[]>([]);
const batchPasswordsVisible = ref(false);

async function handleBatchEnableAccount() {
    if (!selectedIds.value.length) return;
    try {
        const res: any = await batchEnableAccount(selectedIds.value);
        if (res?.success) {
            if (res.passwords?.length) {
                batchPasswords.value = res.passwords;
                batchPasswordsVisible.value = true;
            } else {
                message.success(`已启用 ${res.count} 个账号`);
            }
            await loadMembers();
        } else { message.error("操作失败"); }
    } catch { message.error("操作失败"); }
}

async function handleBatchDisableAccount() {
    if (!selectedIds.value.length) return;
    try {
        const res: any = await batchDisableAccount(selectedIds.value);
        if (res?.success) {
            message.success(`已禁用 ${res.count} 个账号`);
            await loadMembers();
        } else { message.error("操作失败"); }
    } catch { message.error("操作失败"); }
}

function openBatchRoleDialog(action: "assign" | "remove") {
    batchRoleAction.value = action;
    batchRoleDialogOpen.value = true;
}

function openBatchDeptDialog(action: "assign" | "remove") {
    batchDeptAction.value = action;
    batchDeptDialogOpen.value = true;
}

async function handleBatchDeptSelect(deptId: number) {
    if (!selectedIds.value.length) return;
    batchDeptDialogOpen.value = false;
    try {
        const res: any = batchDeptAction.value === "assign"
            ? await batchAssignDept(selectedIds.value, deptId)
            : await batchRemoveDept(selectedIds.value, deptId);
        if (res?.success) {
            message.success(`已${batchDeptAction.value === "assign" ? "分配" : "移除"}部门，影响 ${res.count} 人`);
            await loadMembers();
        } else { message.error("操作失败"); }
    } catch { message.error("操作失败"); }
}

async function handleBatchRoleSelect(roleName: string) {
    if (!selectedIds.value.length) return;
    batchRoleDialogOpen.value = false;
    try {
        const res: any = batchRoleAction.value === "assign"
            ? await batchAssignRole(selectedIds.value, roleName)
            : await batchRemoveRole(selectedIds.value, roleName);
        if (res?.success) {
            message.success(`已${batchRoleAction.value === "assign" ? "分配" : "移除"}角色，影响 ${res.count} 人`);
            await loadMembers();
        } else { message.error("操作失败"); }
    } catch { message.error("操作失败"); }
}

// ---- UI helpers ----

const AVATAR_COLORS = [
    'bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500',
    'bg-pink-500', 'bg-teal-500', 'bg-indigo-500', 'bg-red-400',
    'bg-cyan-500', 'bg-amber-500',
];

function getInitial(name: string): string {
    if (!name) return '?';
    const trimmed = name.trim();
    const first = trimmed.charAt(0);
    return /[a-zA-Z]/.test(first) ? first.toUpperCase() : first;
}

function getAvatarColor(name: string): string {
    if (!name) return AVATAR_COLORS[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

const ROLE_MEMBER_DISPLAY_LIMIT = 10;

const PLATFORM_LABELS: Record<string, string> = {
    wecom: "企业微信",
    dingtalk: "钉钉",
    feishu: "飞书",
    zentao: "禅道",
    gitee: "Gitee",
    web: "Web",
};
const platformLabel = (key: string) => PLATFORM_LABELS[key] || key;

const BUILTIN_ROLE_LABELS: Record<string, string> = {
    admin: "管理员",
    manager: "管理者",
    member: "成员",
};

function roleLabel(roleName: string): string {
    const found = roles.value.find(r => r.name === roleName);
    if (found?.display_name) return found.display_name;
    return BUILTIN_ROLE_LABELS[roleName] || roleName;
}

// ---- Init ----

onMounted(() => {
    loadMembers();
    loadSuggestions();
    loadRoles();
    loadPermissions();
    loadDeptTree();
    loadChannels();
    loadCalendar();
    loadWorkSettings();
});
</script>

<template>
    <div class="space-y-4">
        <!-- 待合并建议提示 -->
        <div v-if="suggestions.length" class="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <div class="flex items-center justify-between cursor-pointer" @click="showSuggestions = !showSuggestions">
                <div class="flex items-center text-amber-700 text-sm font-medium">
                    <AlertTriangle :size="16" class="mr-2" />
                    发现 {{ suggestions.length }} 条疑似重复联系人，点击查看并处理
                </div>
                <span class="text-amber-500 text-xs">{{ showSuggestions ? '收起' : '展开' }}</span>
            </div>
            <div v-if="showSuggestions" class="mt-3 space-y-2">
                <div v-for="s in suggestions" :key="s.id"
                    class="flex items-center justify-between bg-white rounded-lg px-4 py-3 border border-amber-100">
                    <div class="flex items-center gap-3 text-sm text-gray-700">
                        <span class="font-medium">{{ s.source_name || '未知' }}</span>
                        <VortTag color="blue" size="small">{{ s.source_platform }}</VortTag>
                        <span class="text-gray-400">→</span>
                        <span class="font-medium">{{ s.target_name }}</span>
                        <VortTag size="small">{{ s.match_type }}</VortTag>
                        <span class="text-gray-400 text-xs">置信度 {{ (s.confidence * 100).toFixed(0) }}%</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <VortButton size="small" variant="primary" @click.stop="handleAccept(s.id)">
                            <Check :size="14" class="mr-1" /> 合并
                        </VortButton>
                        <VortButton size="small" @click.stop="handleReject(s.id)">
                            <X :size="14" class="mr-1" /> 忽略
                        </VortButton>
                    </div>
                </div>
            </div>
        </div>

        <!-- 主内容区 Tabs -->
        <div class="bg-white rounded-xl p-6">
            <VortTabs v-model:activeKey="activeTab">
                <VortTabPane tab-key="org" tab="组织架构">
                    <div class="flex gap-6" style="min-height: 480px;">
                        <!-- 左侧：部门树 -->
                        <div class="w-60 flex-shrink-0 border-r border-gray-100 pr-4">
                            <div class="flex items-center justify-between mb-3">
                                <div class="text-sm font-medium text-gray-600">组织架构</div>
                                <div class="flex items-center gap-1">
                                    <VortDropdown trigger="click">
                                        <VortButton size="small" :loading="loadingSync">
                                            <RefreshCw :size="14" />
                                        </VortButton>
                                        <template #overlay>
                                            <VortDropdownMenuItem @click="handleSync()">
                                                <Download :size="14" class="mr-2" /> 同步全部通道
                                            </VortDropdownMenuItem>
                                            <VortDropdownMenuSeparator v-if="channels.length" />
                                            <VortDropdownMenuItem v-for="ch in channels" :key="ch.name" @click="handleSync(ch.name)">
                                                <Download :size="14" class="mr-2" /> {{ ch.display_name || ch.name }}
                                            </VortDropdownMenuItem>
                                        </template>
                                    </VortDropdown>
                                    <VortButton size="small" @click="openCreateDeptDialog(null)">
                                        <Plus :size="14" />
                                    </VortButton>
                                </div>
                            </div>
                            <VortSpin :spinning="loadingDepts">
                                <div v-if="deptTree.length" class="space-y-0.5">
                                    <DeptTree
                                        :nodes="deptTree"
                                        :expanded-ids="expandedDeptIds"
                                        :selected-id="selectedDeptId"
                                        :show-all-node="true"
                                        all-node-label="全部成员"
                                        :all-member-count="membersTotal"
                                        @select="handleSelectDept"
                                        @toggle-expand="handleToggleDeptExpand"
                                    />
                                </div>
                                <div v-else class="text-gray-400 text-sm text-center py-8">
                                    暂无部门，同步联系人后自动创建
                                </div>
                            </VortSpin>
                        </div>

                        <!-- 右侧：成员表格 -->
                        <div class="flex-1 min-w-0">
                            <!-- 顶栏：面包屑 + 操作 -->
                            <div class="flex items-center justify-between mb-4">
                                <div class="flex items-center gap-2">
                                    <!-- Breadcrumb -->
                                    <template v-if="selectedDept">
                                        <template v-for="(crumb, idx) in deptBreadcrumb" :key="crumb.id">
                                            <span v-if="idx > 0" class="text-gray-300 text-sm">/</span>
                                            <span
                                                class="text-sm cursor-pointer"
                                                :class="idx === deptBreadcrumb.length - 1 ? 'text-gray-800 font-medium' : 'text-gray-400 hover:text-blue-500'"
                                                @click="handleSelectDept(crumb.id)"
                                            >{{ crumb.name }}</span>
                                        </template>
                                        <span class="text-xs text-gray-400 ml-2">{{ selectedDept.member_count }} 人</span>
                                    </template>
                                    <template v-else>
                                        <h4 class="text-sm font-medium text-gray-800">全部成员</h4>
                                        <span class="text-xs text-gray-400">{{ membersTotal }} 人</span>
                                    </template>
                                </div>
                                <div class="flex items-center gap-2">
                                    <!-- Department actions -->
                                    <template v-if="selectedDept">
                                        <VortButton size="small" @click="openCreateDeptDialog(selectedDept!.id)">
                                            <Plus :size="14" class="mr-1" /> 子部门
                                        </VortButton>
                                        <VortButton size="small" @click="openEditDeptDialog(selectedDept!)">
                                            <Pencil :size="14" class="mr-1" /> 编辑
                                        </VortButton>
                                        <VortButton size="small" @click="handleDeleteDept(selectedDept!.id, selectedDept!.name)">
                                            <Trash2 :size="14" class="mr-1" /> 删除
                                        </VortButton>
                                        <VortButton size="small" variant="primary" @click="addMemberDialogOpen = true; addMemberSearch = ''; addMemberResults = [];">
                                            <UserPlus :size="14" class="mr-1" /> 添加成员
                                        </VortButton>
                                    </template>
                                    <template v-else>
                                        <VortButton size="small" :loading="loadingDedup" @click="handleDedup">
                                            <Search :size="14" class="mr-1" /> 去重扫描
                                        </VortButton>
                                        <VortButton size="small" @click="openCreateMemberDialog">
                                            <UserPlus :size="14" class="mr-1" /> 新增成员
                                        </VortButton>
                                        <VortDropdown trigger="click">
                                            <VortButton size="small" variant="primary" :loading="loadingSync">
                                                <RefreshCw :size="14" class="mr-1" /> 同步联系人 <ChevronDown :size="14" class="ml-1" />
                                            </VortButton>
                                            <template #overlay>
                                                <VortDropdownMenuItem @click="handleSync()">
                                                    <Download :size="14" class="mr-2" /> 同步全部通道
                                                </VortDropdownMenuItem>
                                                <VortDropdownMenuSeparator v-if="channels.length" />
                                                <VortDropdownMenuItem v-for="ch in channels" :key="ch.name" @click="handleSync(ch.name)">
                                                    <Download :size="14" class="mr-2" /> {{ ch.display_name || ch.name }}
                                                </VortDropdownMenuItem>
                                            </template>
                                        </VortDropdown>
                                    </template>
                                </div>
                            </div>

                            <!-- 搜索 + 筛选 -->
                            <div class="flex flex-wrap items-center gap-3 mb-4">
                                <div class="w-66">
                                    <VortInputSearch
                                        v-model="searchText"
                                        placeholder="搜索姓名、邮箱、手机"
                                        allow-clear
                                        @search="handleSearch"
                                        @press-enter="handleSearch"
                                    />
                                </div>
                                <VortSelect
                                    v-model="filterRole"
                                    placeholder="全部角色"
                                    allow-clear
                                    style="width: 140px"
                                    @change="handleSearch"
                                >
                                    <VortSelectOption v-for="r in roles" :key="r.name" :value="r.name">{{ r.display_name }}</VortSelectOption>
                                </VortSelect>
                            </div>

                            <!-- 批量操作栏 -->
                            <div v-if="selectedIds.length" class="flex items-center gap-3 mb-4 px-4 py-2.5 bg-blue-50 rounded-lg border border-blue-200">
                                <span class="text-sm text-blue-700">已选 {{ selectedIds.length }} 项</span>
                                <VortButton size="small" @click="handleBatchEnableAccount">启用登录</VortButton>
                                <VortButton size="small" @click="handleBatchDisableAccount">禁用登录</VortButton>
                                <VortButton size="small" @click="openBatchRoleDialog('assign')">分配角色</VortButton>
                                <VortButton size="small" @click="openBatchRoleDialog('remove')">移除角色</VortButton>
                                <VortButton size="small" @click="openBatchDeptDialog('assign')">分配部门</VortButton>
                                <VortButton size="small" @click="openBatchDeptDialog('remove')">移除部门</VortButton>
                                <VortButton size="small" danger @click="handleBatchDelete">
                                    <Trash2 :size="12" class="mr-1" /> 批量删除
                                </VortButton>
                                <span class="text-xs text-blue-400 cursor-pointer ml-auto" @click="selectedIds = []">取消选择</span>
                            </div>

                            <!-- 成员表格 -->
                            <VortTable :data-source="members" :loading="loadingMembers" row-key="id" :pagination="false" :row-selection="rowSelection">
                                <VortTableColumn label="姓名" prop="name">
                                    <template #default="{ row }">
                                        <div class="flex items-center gap-2">
                                            <span
                                                class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-medium flex-shrink-0"
                                                :class="getAvatarColor(row.name)"
                                            >{{ getInitial(row.name) }}</span>
                                            <div class="min-w-0">
                                                <div class="flex items-center gap-1">
                                                    <span class="text-blue-600 cursor-pointer hover:underline" @click="openMemberDrawer(row.id)">{{ row.name }}</span>
                                                </div>
                                                <div v-if="row.departments?.length" class="text-xs text-gray-400 mt-0.5 line-clamp-2" :title="row.departments.join('、')">
                                                    {{ row.departments.join("、") }}
                                                </div>
                                            </div>
                                        </div>
                                    </template>
                                </VortTableColumn>
                                <VortTableColumn label="职务" prop="position" :width="140">
                                    <template #default="{ row }">
                                        <span class="text-sm text-gray-600">{{ row.position || '-' }}</span>
                                    </template>
                                </VortTableColumn>
                                <VortTableColumn label="角色" prop="roles" :width="160">
                                    <template #default="{ row }">
                                        <VortTag v-for="role in (row.roles || [])" :key="role" class="mr-1" :bordered="false"
                                            :color="role === 'admin' ? 'red' : role === 'manager' ? 'orange' : 'default'">
                                            {{ roleLabel(role) }}
                                        </VortTag>
                                        <span v-if="!row.roles?.length" class="text-gray-400 text-sm">-</span>
                                    </template>
                                </VortTableColumn>
                                <VortTableColumn label="身份绑定" :width="160">
                                    <template #default="{ row }">
                                        <div v-if="row.platform_accounts && Object.keys(row.platform_accounts).length" class="flex flex-wrap gap-1">
                                            <VortTag v-for="(_account, platform) in row.platform_accounts" :key="platform" color="blue" :bordered="false">
                                                <Link :size="12" class="mr-1 inline" /> {{ platformLabel(platform as string) }}
                                            </VortTag>
                                        </div>
                                        <span v-else class="text-gray-400 text-sm">-</span>
                                    </template>
                                </VortTableColumn>
                                <VortTableColumn label="账号状态" :width="90">
                                    <template #default="{ row }">
                                        <VortTag v-if="row.is_account" color="green" :bordered="false">可登录</VortTag>
                                        <VortTag v-else :bordered="false">纯联系人</VortTag>
                                    </template>
                                </VortTableColumn>
                                <VortTableColumn label="操作" :width="220" fixed="right">
                                    <template #default="{ row }">
                                        <div class="flex items-center gap-2 whitespace-nowrap">
                                            <a class="text-sm text-blue-600 cursor-pointer" @click="openMemberDrawer(row.id)">编辑</a>
                                            <vort-divider type="vertical" />
                                            <a class="text-sm text-blue-600 cursor-pointer" @click="openRoleDialog(row)">角色</a>
                                            <vort-divider type="vertical" />
                                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleToggleAccount(row)">{{ row.is_account ? '禁用' : '启用' }}</a>
                                            <template v-if="selectedDeptId">
                                                <vort-divider type="vertical" />
                                                <vort-popconfirm title="确认从该部门移除？" @confirm="handleRemoveMemberFromDept(row.id)">
                                                    <a class="text-sm text-red-500 cursor-pointer">移除</a>
                                                </vort-popconfirm>
                                            </template>
                                            <vort-divider type="vertical" />
                                            <vort-popconfirm title="确认删除该成员？" @confirm="handleDelete(row.id, row.name)">
                                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                                            </vort-popconfirm>
                                        </div>
                                    </template>
                                </VortTableColumn>
                            </VortTable>

                            <!-- 分页 -->
                            <div v-if="membersTotal > membersSize" class="flex justify-end mt-4">
                                <VortPagination
                                    :current="membersPage"
                                    :total="membersTotal"
                                    :page-size="membersSize"
                                    @update:current="(p: number) => { membersPage = p; loadMembers(); }"
                                />
                            </div>
                        </div>
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="roles" tab="角色权限">
                    <div class="flex gap-6" style="min-height: 400px;">
                        <!-- 左侧：角色列表 -->
                        <div class="w-64 flex-shrink-0">
                            <div class="flex items-center justify-between mb-3">
                                <div class="text-sm font-medium text-gray-600">角色列表</div>
                                <VortButton size="small" @click="openCreateRoleDialog">
                                    <Plus :size="14" class="mr-1" /> 新建角色
                                </VortButton>
                            </div>
                            <div class="space-y-2">
                                <div
                                    v-for="(r, idx) in roles" :key="r.id"
                                    class="flex items-center justify-between px-4 py-3 rounded-lg cursor-pointer border transition-colors"
                                    :class="selectedRoleIndex === idx ? 'border-blue-400 bg-blue-50' : 'border-gray-100 hover:bg-gray-50'"
                                    @click="selectedRoleIndex = idx; loadRoleMembers(r.name)"
                                >
                                    <div>
                                        <div class="text-sm font-medium text-gray-800">{{ r.display_name }}</div>
                                        <div class="text-xs text-gray-400 mt-0.5">
                                            {{ r.name }}
                                            <VortTag v-if="r.is_builtin" size="small" class="ml-1">内置</VortTag>
                                            <VortTag v-else-if="r.source === 'custom'" size="small" color="blue" class="ml-1">自定义</VortTag>
                                            <VortTag v-else size="small" color="cyan" class="ml-1">{{ r.source }}</VortTag>
                                        </div>
                                    </div>
                                    <VortTag size="small">{{ r.member_count }} 人</VortTag>
                                </div>
                                <div v-if="!roles.length && !loadingRoles" class="text-gray-400 text-sm text-center py-8">暂无角色</div>
                            </div>
                        </div>

                        <!-- 右侧：选中角色详情 -->
                        <div class="flex-1 min-w-0">
                            <template v-if="selectedRole">
                                <div class="flex items-center justify-between mb-4">
                                    <div>
                                        <h4 class="text-base font-medium text-gray-800">{{ selectedRole.display_name }}</h4>
                                        <div class="text-xs text-gray-400 mt-1">
                                            <span v-if="selectedRole.is_builtin">内置角色</span>
                                            <span v-else-if="selectedRole.source === 'custom'">自定义角色</span>
                                            <span v-else>来源: {{ selectedRole.source }}</span>
                                            <span v-if="selectedRole.is_admin" class="ml-2 text-red-500">拥有全部权限</span>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <VortButton size="small" @click="openEditRoleDialog(selectedRole!)">
                                            <Pencil :size="14" class="mr-1" /> 编辑
                                        </VortButton>
                                        <VortButton
                                            v-if="!selectedRole.is_builtin"
                                            size="small" danger
                                            @click="handleDeleteRole(selectedRole!)"
                                        >
                                            <Trash2 :size="14" class="mr-1" /> 删除
                                        </VortButton>
                                    </div>
                                </div>

                                <!-- 权限分组展示 -->
                                <div class="mb-6">
                                    <!-- 系统权限 -->
                                    <div v-if="groupedPermissions.coreGroups.length" class="mb-4">
                                        <div class="flex items-center gap-2 mb-2">
                                            <VortCheckbox
                                                :checked="isSectionAllSelected(groupedPermissions.coreGroups)"
                                                :indeterminate="isSectionPartial(groupedPermissions.coreGroups)"
                                                :disabled="!canEditPermissions"
                                                @change="toggleSection(groupedPermissions.coreGroups)"
                                            />
                                            <span class="text-sm font-medium text-gray-500">系统权限</span>
                                        </div>
                                        <div class="border border-gray-200 rounded-lg divide-y divide-gray-100">
                                            <div v-for="group in groupedPermissions.coreGroups" :key="group.key" class="flex items-center">
                                                <div class="w-42 flex-shrink-0 px-4 py-2.5 bg-gray-50/60 border-r border-gray-100">
                                                    <VortCheckbox
                                                        :checked="isGroupAllSelected(group)"
                                                        :indeterminate="isGroupPartial(group)"
                                                        :disabled="!canEditPermissions"
                                                        @change="toggleGroup(group)"
                                                    >
                                                        <span class="text-xs font-medium text-gray-600">{{ group.label }}</span>
                                                    </VortCheckbox>
                                                </div>
                                                <div class="flex-1 px-4 py-2.5 flex flex-wrap gap-x-4 gap-y-1">
                                                    <VortCheckbox
                                                        v-for="p in group.permissions" :key="p.code"
                                                        :checked="isPermSelected(p.code)"
                                                        :disabled="!canEditPermissions"
                                                        @change="togglePerm(p.code)"
                                                    >{{ p.display_name }}</VortCheckbox>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- 插件权限 -->
                                    <div v-if="groupedPermissions.pluginGroups.length">
                                        <div class="flex items-center gap-2 mb-2">
                                            <VortCheckbox
                                                :checked="isSectionAllSelected(groupedPermissions.pluginGroups)"
                                                :indeterminate="isSectionPartial(groupedPermissions.pluginGroups)"
                                                :disabled="!canEditPermissions"
                                                @change="toggleSection(groupedPermissions.pluginGroups)"
                                            />
                                            <span class="text-sm font-medium text-gray-500">插件权限</span>
                                        </div>
                                        <div class="border border-gray-200 rounded-lg divide-y divide-gray-100">
                                            <div v-for="group in groupedPermissions.pluginGroups" :key="group.key" class="flex items-center">
                                                <div class="w-42 flex-shrink-0 px-4 py-2.5 bg-gray-50/60 border-r border-gray-100">
                                                    <VortCheckbox
                                                        :checked="isGroupAllSelected(group)"
                                                        :indeterminate="isGroupPartial(group)"
                                                        :disabled="!canEditPermissions"
                                                        @change="toggleGroup(group)"
                                                    >
                                                        <span class="text-xs font-medium text-gray-600">{{ group.label }}</span>
                                                    </VortCheckbox>
                                                </div>
                                                <div class="flex-1 px-4 py-2.5 flex flex-wrap gap-x-4 gap-y-1">
                                                    <VortCheckbox
                                                        v-for="p in group.permissions" :key="p.code"
                                                        :checked="isPermSelected(p.code)"
                                                        :disabled="!canEditPermissions"
                                                        @change="togglePerm(p.code)"
                                                    >{{ p.display_name }}</VortCheckbox>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- 保存/取消 -->
                                    <div v-if="hasPermChanges" class="mt-3 flex items-center gap-2">
                                        <VortButton variant="primary" size="small" :loading="savingPermsInline" @click="savePermissionsInline">保存权限</VortButton>
                                        <VortButton size="small" @click="cancelPermEdit">取消</VortButton>
                                    </div>
                                </div>

                                <!-- 该角色下的成员 -->
                                <div>
                                    <div class="text-sm font-medium text-gray-600 mb-2">成员 ({{ selectedRole.member_count }})</div>
                                    <VortSpin :spinning="loadingRoleMembers">
                                        <div class="flex flex-wrap gap-2">
                                            <VortTag
                                                v-for="m in roleMembers.slice(0, ROLE_MEMBER_DISPLAY_LIMIT)"
                                                :key="m.id"
                                                class="cursor-pointer"
                                                @click="openMemberDrawer(m.id)"
                                            >
                                                <span
                                                    class="inline-flex items-center justify-center w-4 h-4 rounded-full text-white mr-1 flex-shrink-0"
                                                    :class="getAvatarColor(m.name)"
                                                    style="font-size: 10px;"
                                                >{{ getInitial(m.name) }}</span>
                                                {{ m.name }}
                                            </VortTag>
                                            <span
                                                v-if="selectedRole.member_count > roleMembers.length || roleMembers.length > ROLE_MEMBER_DISPLAY_LIMIT"
                                                class="text-gray-400 text-sm leading-6"
                                            >等其他 {{ selectedRole.member_count - Math.min(roleMembers.length, ROLE_MEMBER_DISPLAY_LIMIT) }} 名成员</span>
                                            <span v-if="!roleMembers.length && !loadingRoleMembers" class="text-gray-400 text-sm">暂无成员</span>
                                        </div>
                                    </VortSpin>
                                </div>
                            </template>
                            <div v-else class="text-gray-400 text-sm text-center py-16">请选择一个角色查看详情</div>
                        </div>
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="calendar" tab="企业日历">
                    <!-- 工时设置 — 展示模式 -->
                    <div v-if="workSettings && !editingWorkSettings" class="flex items-center gap-6 mb-6 p-4 bg-gray-50 rounded-lg">
                        <div><span class="text-xs text-gray-400">时区</span><div class="text-sm text-gray-800 mt-0.5">{{ workSettings.timezone }}</div></div>
                        <div><span class="text-xs text-gray-400">工作时间</span><div class="text-sm text-gray-800 mt-0.5">{{ workSettings.work_start }} - {{ workSettings.work_end }}</div></div>
                        <div><span class="text-xs text-gray-400">午休时间</span><div class="text-sm text-gray-800 mt-0.5">{{ workSettings.lunch_start }} - {{ workSettings.lunch_end }}</div></div>
                        <div><span class="text-xs text-gray-400">工作日</span><div class="text-sm text-gray-800 mt-0.5">{{ workSettings.work_days.split(',').map((d: string) => ['','周一','周二','周三','周四','周五','周六','周日'][+d] || d).join('、') }}</div></div>
                        <div class="ml-auto flex-shrink-0">
                            <VortButton size="small" @click="startEditWorkSettings">
                                <Pencil :size="14" class="mr-1" /> 编辑
                            </VortButton>
                        </div>
                    </div>

                    <!-- 工时设置 — 编辑模式 -->
                    <div v-if="editingWorkSettings" class="mb-6 p-5 bg-gray-50 rounded-lg">
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-4">
                            <div>
                                <label class="block text-xs text-gray-500 mb-1">时区</label>
                                <VortInput v-model="workSettingsForm.timezone" placeholder="如 Asia/Shanghai" />
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 mb-1">上班时间</label>
                                <VortTimePicker
                                    v-model="workSettingsForm.work_start"
                                    format="HH:mm"
                                    value-format="HH:mm"
                                    :show-second="false"
                                    placeholder="如 09:00"
                                />
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 mb-1">下班时间</label>
                                <VortTimePicker
                                    v-model="workSettingsForm.work_end"
                                    format="HH:mm"
                                    value-format="HH:mm"
                                    :show-second="false"
                                    placeholder="如 18:00"
                                />
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 mb-1">午休开始</label>
                                <VortTimePicker
                                    v-model="workSettingsForm.lunch_start"
                                    format="HH:mm"
                                    value-format="HH:mm"
                                    :show-second="false"
                                    placeholder="如 12:00"
                                />
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 mb-1">午休结束</label>
                                <VortTimePicker
                                    v-model="workSettingsForm.lunch_end"
                                    format="HH:mm"
                                    value-format="HH:mm"
                                    :show-second="false"
                                    placeholder="如 13:30"
                                />
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 mb-1">工作日</label>
                                <div class="flex flex-wrap gap-2 mt-1">
                                    <span
                                        v-for="opt in weekDayOptions" :key="opt.value"
                                        class="inline-flex items-center justify-center w-10 h-8 rounded-md text-xs cursor-pointer transition-colors select-none"
                                        :class="workSettingsForm.work_days.includes(opt.value)
                                            ? 'bg-blue-500 text-white'
                                            : 'bg-white text-gray-600 border border-gray-200 hover:border-blue-300'"
                                        @click="workSettingsForm.work_days.includes(opt.value)
                                            ? workSettingsForm.work_days = workSettingsForm.work_days.filter(d => d !== opt.value)
                                            : workSettingsForm.work_days.push(opt.value)"
                                    >{{ opt.label }}</span>
                                </div>
                            </div>
                        </div>
                        <div class="flex justify-end gap-3 mt-5">
                            <VortButton @click="cancelEditWorkSettings">取消</VortButton>
                            <VortButton variant="primary" :loading="savingWorkSettings" @click="handleSaveWorkSettings">保存</VortButton>
                        </div>
                    </div>

                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <h4 class="text-base font-medium text-gray-800">{{ calendarYear }} 年节假日</h4>
                            <div class="flex items-center gap-1">
                                <VortButton size="small" @click="calendarYear--; loadCalendar()">←</VortButton>
                                <VortButton size="small" @click="calendarYear++; loadCalendar()">→</VortButton>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <VortButton :loading="syncingHolidays" @click="handleSyncHolidays">
                                <CloudDownload :size="14" class="mr-1" /> 同步法定节假日
                            </VortButton>
                            <VortButton variant="primary" @click="openCalendarDialog">
                                <Plus :size="14" class="mr-1" /> 手动添加
                            </VortButton>
                        </div>
                    </div>

                    <VortSpin :spinning="loadingCalendar">
                        <div v-if="calendarEntries.length">
                            <VortTable :data-source="calendarEntries" :loading="false" :pagination="false" row-key="id">
                                <VortTableColumn label="日期" prop="date" :width="140">
                                    <template #default="{ row }">
                                        <div class="flex items-center gap-2">
                                            <Calendar :size="14" class="text-gray-400" />
                                            <span>{{ row.date }}</span>
                                        </div>
                                    </template>
                                </VortTableColumn>
                                <VortTableColumn label="类型" :width="120">
                                    <template #default="{ row }">
                                        <VortTag :color="dayTypeColor(row.day_type)" size="small">{{ dayTypeLabel(row.day_type) }}</VortTag>
                                    </template>
                                </VortTableColumn>
                                <VortTableColumn label="名称" prop="name" />
                                <VortTableColumn label="操作" :width="80" fixed="right">
                                    <template #default="{ row }">
                                        <VortPopconfirm title="确认删除？" @confirm="handleDeleteCalendar(row.id)">
                                            <a class="text-sm text-red-500 cursor-pointer">删除</a>
                                        </VortPopconfirm>
                                    </template>
                                </VortTableColumn>
                            </VortTable>
                        </div>
                        <div v-else class="text-gray-400 text-sm text-center py-16">
                            暂无日历数据，点击「同步法定节假日」或手动添加
                        </div>
                    </VortSpin>
                </VortTabPane>
            </VortTabs>
        </div>

        <!-- 成员详情抽屉 -->
        <VortDrawer :open="drawerOpen" title="成员详情" :width="480" @update:open="drawerOpen = $event">
            <template v-if="drawerLoading">
                <div class="flex items-center justify-center py-16 text-gray-400">加载中...</div>
            </template>
            <template v-else-if="currentMember">
                <div class="space-y-4">
                    <!-- 基本信息编辑 -->
                    <div class="rounded-lg border border-gray-100 bg-white">
                        <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50/60 rounded-t-lg">
                            <User :size="15" class="text-gray-400" />
                            <h4 class="text-sm font-semibold text-gray-700">基本信息</h4>
                        </div>
                        <div class="px-4 py-4">
                            <VortForm label-width="60px">
                                <VortFormItem label="姓名">
                                    <VortInput v-model="editForm.name" placeholder="请输入姓名" />
                                </VortFormItem>
                                <VortFormItem label="邮箱">
                                    <VortInput v-model="editForm.email" placeholder="请输入邮箱" />
                                </VortFormItem>
                                <VortFormItem label="手机">
                                    <VortInput v-model="editForm.phone" placeholder="请输入手机号" />
                                </VortFormItem>
                                <VortFormItem label="职位">
                                    <VortInput v-model="editForm.position" placeholder="留空则自动从平台身份获取" />
                                </VortFormItem>
                                <VortFormItem>
                                    <VortButton variant="primary" size="small" :loading="savingEdit" @click="handleSaveEdit">保存</VortButton>
                                </VortFormItem>
                            </VortForm>
                        </div>
                    </div>

                    <!-- 部门 -->
                    <div class="rounded-lg border border-gray-100 bg-white">
                        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50/60 rounded-t-lg">
                            <div class="flex items-center gap-2">
                                <FolderTree :size="15" class="text-gray-400" />
                                <h4 class="text-sm font-semibold text-gray-700">部门</h4>
                            </div>
                            <VortButton size="small" @click="drawerDeptDialogOpen = true">
                                <Plus :size="12" class="mr-1" /> 添加
                            </VortButton>
                        </div>
                        <div class="px-4 py-3">
                            <div class="flex flex-wrap gap-2">
                                <VortTag
                                    v-for="dept in currentMember.departments" :key="dept.id"
                                    closable
                                    @close="handleRemoveDeptFromMember(dept.id)"
                                >
                                    {{ dept.name }}
                                </VortTag>
                                <span v-if="!currentMember.departments?.length" class="text-gray-400 text-sm py-0.5">暂未分配部门</span>
                            </div>
                        </div>
                    </div>

                    <!-- 角色 -->
                    <div class="rounded-lg border border-gray-100 bg-white">
                        <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50/60 rounded-t-lg">
                            <Shield :size="15" class="text-gray-400" />
                            <h4 class="text-sm font-semibold text-gray-700">角色</h4>
                        </div>
                        <div class="px-4 py-3">
                            <div class="flex flex-wrap gap-2">
                                <VortTag
                                    v-for="role in currentMember.roles" :key="role"
                                    :bordered="false"
                                    :color="role === 'admin' ? 'red' : role === 'manager' ? 'orange' : 'default'"
                                    closable
                                    @close="handleRemoveRole(currentMember!.id, role)"
                                >
                                    {{ roleLabel(role) }}
                                </VortTag>
                                <span v-if="!currentMember.roles.length" class="text-gray-400 text-sm py-0.5">暂无角色</span>
                            </div>
                            <div v-if="roles.filter(r => !currentMember!.roles.includes(r.name)).length" class="mt-3 pt-3 border-t border-gray-100">
                                <div class="flex flex-wrap gap-1">
                                    <VortButton
                                        v-for="r in roles.filter(r => !currentMember!.roles.includes(r.name))"
                                        :key="r.name"
                                        size="small"
                                        @click="handleAssignRole(currentMember!.id, r.name)"
                                    >
                                        + {{ r.display_name }}
                                    </VortButton>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 账号操作 -->
                    <div class="rounded-lg border border-gray-100 bg-white">
                        <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50/60 rounded-t-lg">
                            <Key :size="15" class="text-gray-400" />
                            <h4 class="text-sm font-semibold text-gray-700">账号</h4>
                        </div>
                        <div class="px-4 py-3">
                            <div class="flex items-center gap-3">
                                <VortTag v-if="currentMember.is_account" color="green" :bordered="false">
                                    <UserCheck :size="12" class="mr-1" /> 可登录
                                </VortTag>
                                <VortTag v-else :bordered="false">
                                    <UserX :size="12" class="mr-1" /> 纯联系人
                                </VortTag>
                                <VortButton size="small" @click="handleToggleAccount(currentMember as any)">
                                    {{ currentMember.is_account ? '禁用登录' : '启用登录' }}
                                </VortButton>
                                <VortButton v-if="currentMember.is_account" size="small" @click="handleResetPassword(currentMember.id)">
                                    <Key :size="12" class="mr-1" /> 重置密码
                                </VortButton>
                            </div>
                            <div v-if="currentMember.is_account" class="mt-2 text-xs text-gray-400">
                                <Lock :size="12" class="inline mr-1" />
                                {{ currentMember.has_password ? '已设置密码' : '未设置密码' }}
                            </div>
                        </div>
                    </div>

                    <!-- 平台身份 -->
                    <div class="rounded-lg border border-gray-100 bg-white">
                        <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50/60 rounded-t-lg">
                            <IdCard :size="15" class="text-gray-400" />
                            <h4 class="text-sm font-semibold text-gray-700">平台身份</h4>
                        </div>
                        <div class="px-4 py-3">
                            <div v-if="currentMember.identities.length" class="space-y-2">
                                <div v-for="ident in currentMember.identities" :key="ident.id"
                                    class="bg-gray-50 rounded-lg px-4 py-3 text-sm">
                                    <div class="flex items-center gap-2 mb-1">
                                        <VortTag color="blue" size="small" :bordered="false">{{ platformLabel(ident.platform) }}</VortTag>
                                        <span class="font-medium">{{ ident.platform_display_name || ident.platform_username }}</span>
                                    </div>
                                    <div class="text-xs text-gray-400 space-y-0.5">
                                        <div v-if="ident.platform_user_id">ID: {{ ident.platform_user_id }}</div>
                                        <div v-if="ident.platform_email">邮箱: {{ ident.platform_email }}</div>
                                        <div v-if="ident.platform_position">职位: {{ ident.platform_position }}</div>
                                        <div v-if="ident.platform_department">部门: {{ ident.platform_department }}</div>
                                    </div>
                                </div>
                            </div>
                            <span v-else class="text-gray-400 text-sm">未绑定任何平台</span>
                        </div>
                    </div>
                </div>
            </template>
        </VortDrawer>

        <!-- 角色分配弹窗（单选） -->
        <VortDialog :open="roleDialogOpen" title="角色管理" :footer="false" @update:open="roleDialogOpen = $event">
            <template v-if="roleDialogMember">
                <div class="mb-3 text-sm text-gray-600">
                    为 <span class="font-medium text-gray-800">{{ roleDialogMember.name }}</span> 分配角色
                </div>
                <VortSpin :spinning="roleDialogLoading">
                    <div class="space-y-2">
                        <div
                            v-for="r in roles" :key="r.name"
                            class="flex items-center justify-between px-4 py-3 rounded-lg border transition-colors cursor-pointer"
                            :class="roleDialogMember.roles.includes(r.name) ? 'border-blue-400 bg-blue-50' : 'border-gray-100 hover:bg-gray-50'"
                            @click="handleRoleDialogToggle(r.name)"
                        >
                            <div>
                                <div class="text-sm font-medium" :class="roleDialogMember.roles.includes(r.name) ? 'text-blue-700' : 'text-gray-700'">
                                    {{ r.display_name }}
                                </div>
                                <div class="text-xs text-gray-400">{{ r.name }}</div>
                            </div>
                            <div
                                class="w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0"
                                :class="roleDialogMember.roles.includes(r.name) ? 'border-blue-500 bg-blue-500' : 'border-gray-300'"
                            >
                                <div v-if="roleDialogMember.roles.includes(r.name)" class="w-1.5 h-1.5 rounded-full bg-white" />
                            </div>
                        </div>
                    </div>
                </VortSpin>
            </template>
        </VortDialog>

        <!-- 批量角色弹窗 -->
        <VortDialog :open="batchRoleDialogOpen" :title="batchRoleAction === 'assign' ? '批量分配角色' : '批量移除角色'" @update:open="batchRoleDialogOpen = $event">
            <div class="mb-3 text-sm text-gray-600">
                选择要{{ batchRoleAction === 'assign' ? '分配' : '移除' }}的角色（影响 {{ selectedIds.length }} 人）
            </div>
            <div class="space-y-2">
                <div
                    v-for="r in roles" :key="r.name"
                    class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer"
                    @click="handleBatchRoleSelect(r.name)"
                >
                    <div>
                        <div class="text-sm font-medium text-gray-700">{{ r.display_name }}</div>
                        <div class="text-xs text-gray-400">{{ r.name }}</div>
                    </div>
                </div>
            </div>
        </VortDialog>

        <!-- 批量部门弹窗 -->
        <VortDialog :open="batchDeptDialogOpen" :title="batchDeptAction === 'assign' ? '批量分配部门' : '批量移除部门'" :footer="false" @update:open="batchDeptDialogOpen = $event">
            <div class="mb-3 text-sm text-gray-600">
                选择要{{ batchDeptAction === 'assign' ? '分配' : '移除' }}的部门（影响 {{ selectedIds.length }} 人）
            </div>
            <div class="max-h-80 overflow-y-auto">
                <DeptTree
                    :nodes="deptTree"
                    :expanded-ids="expandedDeptIds"
                    :selected-id="null"
                    @select="(id: number | null) => { if (id !== null) handleBatchDeptSelect(id); }"
                    @toggle-expand="handleToggleDeptExpand"
                />
                <div v-if="!deptTree.length" class="text-gray-400 text-sm text-center py-4">暂无部门</div>
            </div>
        </VortDialog>

        <!-- 详情抽屉：添加到部门弹窗 -->
        <VortDialog :open="drawerDeptDialogOpen" title="添加到部门" :footer="false" @update:open="drawerDeptDialogOpen = $event">
            <div class="max-h-80 overflow-y-auto">
                <DeptTree
                    :nodes="deptTree"
                    :expanded-ids="expandedDeptIds"
                    :selected-id="null"
                    @select="(id: number | null) => { if (id !== null) { handleAddDeptToMember(id); drawerDeptDialogOpen = false; } }"
                    @toggle-expand="handleToggleDeptExpand"
                />
                <div v-if="!deptTree.length" class="text-gray-400 text-sm text-center py-4">暂无部门</div>
            </div>
        </VortDialog>

        <!-- 角色编辑弹窗 -->
        <VortDialog
            :open="roleEditDialogOpen"
            :title="roleEditMode === 'create' ? '新建角色' : '编辑角色'"
            :ok-text="roleEditMode === 'create' ? '创建' : '保存'"
            :confirm-loading="savingRole"
            :width="roleEditMode === 'create' ? 640 : undefined"
            @update:open="roleEditDialogOpen = $event"
            @ok="handleSaveRole"
            @cancel="roleEditDialogOpen = false"
        >
            <div class="space-y-4">
                <div v-if="roleEditMode === 'create'">
                    <label class="block text-xs text-gray-500 mb-1">角色标识（英文，创建后不可修改）</label>
                    <VortInput v-model="roleEditForm.name" placeholder="如 developer、tester" />
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">显示名称</label>
                    <VortInput v-model="roleEditForm.display_name" placeholder="如 开发者、测试人员" />
                </div>
                <div v-if="roleEditMode === 'create'">
                    <label class="block text-xs text-gray-500 mb-2">权限分配</label>
                    <div v-if="allPermissions.length" class="max-h-80 overflow-y-auto">
                        <!-- 系统权限 -->
                        <div v-if="groupedPermissions.coreGroups.length" class="mb-3">
                            <div class="flex items-center gap-2 mb-1">
                                <VortCheckbox
                                    :checked="isDialogSectionAllSelected(groupedPermissions.coreGroups)"
                                    :indeterminate="isDialogSectionPartial(groupedPermissions.coreGroups)"
                                    @change="toggleDialogSection(groupedPermissions.coreGroups)"
                                />
                                <span class="text-xs font-medium text-gray-400">系统权限</span>
                            </div>
                            <div class="border border-gray-200 rounded-lg divide-y divide-gray-100">
                                <div v-for="group in groupedPermissions.coreGroups" :key="group.key" class="flex items-center">
                                    <div class="w-34 flex-shrink-0 px-3 py-2 bg-gray-50/60 border-r border-gray-100">
                                        <VortCheckbox
                                            :checked="isDialogGroupAllSelected(group)"
                                            :indeterminate="isDialogGroupPartial(group)"
                                            @change="toggleDialogGroup(group)"
                                        >
                                            <span class="text-xs font-medium text-gray-600">{{ group.label }}</span>
                                        </VortCheckbox>
                                    </div>
                                    <div class="flex-1 px-3 py-2 flex flex-wrap gap-x-3 gap-y-0.5">
                                        <VortCheckbox
                                            v-for="p in group.permissions" :key="p.code"
                                            :checked="roleEditForm.permissions.includes(p.code)"
                                            @change="togglePermission(p.code)"
                                        >{{ p.display_name }}</VortCheckbox>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <!-- 插件权限 -->
                        <div v-if="groupedPermissions.pluginGroups.length">
                            <div class="flex items-center gap-2 mb-1">
                                <VortCheckbox
                                    :checked="isDialogSectionAllSelected(groupedPermissions.pluginGroups)"
                                    :indeterminate="isDialogSectionPartial(groupedPermissions.pluginGroups)"
                                    @change="toggleDialogSection(groupedPermissions.pluginGroups)"
                                />
                                <span class="text-xs font-medium text-gray-400">插件权限</span>
                            </div>
                            <div class="border border-gray-200 rounded-lg divide-y divide-gray-100">
                                <div v-for="group in groupedPermissions.pluginGroups" :key="group.key" class="flex items-center">
                                    <div class="w-34 flex-shrink-0 px-3 py-2 bg-gray-50/60 border-r border-gray-100">
                                        <VortCheckbox
                                            :checked="isDialogGroupAllSelected(group)"
                                            :indeterminate="isDialogGroupPartial(group)"
                                            @change="toggleDialogGroup(group)"
                                        >
                                            <span class="text-xs font-medium text-gray-600">{{ group.label }}</span>
                                        </VortCheckbox>
                                    </div>
                                    <div class="flex-1 px-3 py-2 flex flex-wrap gap-x-3 gap-y-0.5">
                                        <VortCheckbox
                                            v-for="p in group.permissions" :key="p.code"
                                            :checked="roleEditForm.permissions.includes(p.code)"
                                            @change="togglePermission(p.code)"
                                        >{{ p.display_name }}</VortCheckbox>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-else class="text-gray-400 text-sm py-2">暂无可分配的权限</div>
                </div>
            </div>
        </VortDialog>

        <!-- 部门编辑弹窗 -->
        <VortDialog
            :open="deptDialogOpen"
            :title="deptDialogMode === 'create' ? '新建部门' : '编辑部门'"
            :ok-text="deptDialogMode === 'create' ? '创建' : '保存'"
            :confirm-loading="savingDept"
            @update:open="deptDialogOpen = $event"
            @ok="handleSaveDept"
            @cancel="deptDialogOpen = false"
        >
            <div>
                <label class="block text-xs text-gray-500 mb-1">部门名称</label>
                <VortInput
                    v-model="deptDialogForm.name"
                    placeholder="请输入部门名称"
                    @press-enter="handleSaveDept"
                />
            </div>
        </VortDialog>

        <!-- 添加成员到部门弹窗 -->
        <VortDialog
            :open="addMemberDialogOpen"
            title="添加成员到部门"
            :footer="false"
            @update:open="addMemberDialogOpen = $event"
        >
            <div class="space-y-3">
                <div class="flex items-center gap-2">
                    <VortInputSearch
                        v-model="addMemberSearch"
                        placeholder="搜索成员姓名、邮箱"
                        class="flex-1"
                        @search="handleSearchAddMember"
                        @press-enter="handleSearchAddMember"
                    />
                </div>
                <div v-if="addMemberResults.length" class="max-h-64 overflow-y-auto space-y-1">
                    <div
                        v-for="m in addMemberResults" :key="m.id"
                        class="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 text-sm"
                    >
                        <div>
                            <span class="font-medium text-gray-800">{{ m.name }}</span>
                            <span v-if="m.email" class="text-gray-400 ml-2 text-xs">{{ m.email }}</span>
                        </div>
                        <VortButton size="small" variant="primary" @click="handleAddMemberToDept(m.id)">
                            <Plus :size="12" class="mr-1" /> 添加
                        </VortButton>
                    </div>
                </div>
                <div v-else-if="addMemberSearch && !addMemberLoading" class="text-gray-400 text-sm text-center py-4">未找到匹配成员</div>
            </div>
        </VortDialog>

        <!-- 新增日历条目弹窗 -->
        <VortDialog
            :open="calendarDialogOpen"
            title="添加日历条目"
            :ok-text="'添加'"
            :confirm-loading="savingCalendar"
            @update:open="calendarDialogOpen = $event"
            @ok="handleSaveCalendar"
        >
            <div class="space-y-4">
                <div>
                    <label class="block text-xs text-gray-500 mb-1">日期</label>
                    <VortDatePicker v-model="calendarForm.date" value-format="YYYY-MM-DD" placeholder="请选择日期" style="width: 100%" />
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">类型</label>
                    <VortSelect v-model="calendarForm.day_type" style="width: 100%">
                        <VortSelectOption v-for="opt in dayTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                    </VortSelect>
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">名称</label>
                    <VortInput v-model="calendarForm.name" placeholder="如：国庆节、中秋调休补班" />
                </div>
            </div>
        </VortDialog>

        <!-- 新增成员弹窗 -->
        <VortDialog
            :open="createMemberDialogOpen"
            title="新增成员"
            :ok-text="'创建'"
            :confirm-loading="savingCreateMember"
            @update:open="createMemberDialogOpen = $event"
            @ok="handleCreateMember"
        >
            <div class="space-y-4">
                <div>
                    <label class="block text-xs text-gray-500 mb-1">姓名 <span class="text-red-500">*</span></label>
                    <VortInput v-model="createMemberForm.name" placeholder="请输入姓名" />
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">邮箱</label>
                    <VortInput v-model="createMemberForm.email" placeholder="请输入邮箱" />
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">手机</label>
                    <VortInput v-model="createMemberForm.phone" placeholder="请输入手机号" />
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">职务</label>
                    <VortInput v-model="createMemberForm.position" placeholder="请输入职务" />
                </div>
                <div class="flex items-center gap-2">
                    <VortSwitch v-model:checked="createMemberForm.is_account" />
                    <span class="text-sm text-gray-600">允许登录系统</span>
                </div>
            </div>
        </VortDialog>

        <!-- 向导式创建成员 -->
        <MemberWizard
            :open="wizardOpen"
            @update:open="wizardOpen = $event"
            @complete="async () => { await Promise.all([loadMembers(), loadDeptTree()]); }"
        />

        <!-- 单个成员密码展示弹窗 -->
        <VortDialog
            :open="generatedPassword.visible"
            title="初始密码"
            width="small"
            @update:open="(v: boolean) => { if (!v) closeGeneratedPassword(); }"
        >
            <div class="space-y-3">
                <p class="text-sm text-gray-600">
                    成员 <span class="font-semibold">{{ generatedPassword.memberName }}</span> 的初始密码已生成，请妥善保管。
                </p>
                <div class="flex items-center gap-2 bg-gray-50 px-3 py-2 rounded-lg border">
                    <code class="flex-1 text-base font-mono tracking-wider select-all">{{ generatedPassword.password }}</code>
                    <VortButton size="small" @click="navigator.clipboard.writeText(generatedPassword.password); message.success('已复制')">复制</VortButton>
                </div>
                <p class="text-xs text-amber-600">该密码仅展示一次，关闭后无法再次查看。成员首次登录后需强制修改密码。</p>
            </div>
            <template #footer>
                <VortButton type="primary" @click="closeGeneratedPassword">知道了</VortButton>
            </template>
        </VortDialog>

        <!-- 批量启用密码展示弹窗 -->
        <VortDialog
            :open="batchPasswordsVisible"
            title="初始密码列表"
            width="default"
            @update:open="(v: boolean) => { if (!v) batchPasswordsVisible = false; }"
        >
            <p class="text-sm text-gray-600 mb-3">以下成员已启用登录并生成了初始密码，请妥善保管。</p>
            <div class="border rounded-lg overflow-hidden">
                <table class="w-full text-sm">
                    <thead class="bg-gray-50 border-b">
                        <tr>
                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500">姓名</th>
                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500">初始密码</th>
                            <th class="px-3 py-2 text-right text-xs font-medium text-gray-500">操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="item in batchPasswords" :key="item.id" class="border-b last:border-b-0">
                            <td class="px-3 py-2 font-medium">{{ item.name }}</td>
                            <td class="px-3 py-2 font-mono tracking-wider select-all">{{ item.password }}</td>
                            <td class="px-3 py-2 text-right">
                                <VortButton size="small" @click="navigator.clipboard.writeText(item.password); message.success('已复制')">复制</VortButton>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <p class="text-xs text-amber-600 mt-3">这些密码仅展示一次，关闭后无法再次查看。成员首次登录后需强制修改密码。</p>
            <template #footer>
                <VortButton size="small" @click="navigator.clipboard.writeText(batchPasswords.map(p => `${p.name}: ${p.password}`).join('\n')); message.success('已全部复制')">全部复制</VortButton>
                <VortButton type="primary" @click="batchPasswordsVisible = false">知道了</VortButton>
            </template>
        </VortDialog>
    </div>
</template>

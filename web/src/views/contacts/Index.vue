<script setup lang="ts">
import { ref, onMounted, computed, watch } from "vue";
import {
    getMembers, getMember, createMember, updateMember, resetMemberPassword,
    toggleMemberAccount, assignMemberRole, removeMemberRole,
    deleteMember, batchDeleteMembers, batchEnableAccount,
    batchDisableAccount, batchAssignRole, batchRemoveRole,
    batchAssignDept, batchRemoveDept,
    getRoles, getPermissions, createRole, updateRole, deleteRole,
    syncContacts, getSuggestions,
    acceptSuggestion, rejectSuggestion, dedupContacts,
    getDepartmentTree, createDepartment,
    updateDepartment, deleteDepartment, addDepartmentMember,
    removeDepartmentMember, getChannels,
    getOrgCalendar, createOrgCalendarEntry, deleteOrgCalendarEntry, syncHolidays, getWorkSettings, updateWorkSettings,
} from "@/api";
import {
    RefreshCw, Search, Shield, UserCheck, UserX, Key,
    AlertTriangle, Check, X, Link, Lock, Trash2,
    ChevronDown, FolderTree, Plus, Pencil, UserPlus,
    Download, Calendar, CloudDownload, User, IdCard,
} from "lucide-vue-next";
import { message, dialog } from "@/components/vort";
import { DeptTree } from "@/components/vort-biz/dept-tree";
import { MemberWizard } from "@/components/vort-biz/member-wizard";
import type { DeptNode } from "@/components/vort-biz/dept-tree";

// ---- 类型 ----

interface MemberItem {
    id: string;
    name: string;
    email: string;
    phone: string;
    position: string;
    status: string;
    is_account: boolean;
    has_password: boolean;
    roles: string[];
    platform_accounts: Record<string, string>;
    departments: string[];
    created_at: string;
}

interface MemberDetail extends Omit<MemberItem, 'departments'> {
    avatar_url: string;
    permissions: string[];
    remote_node_id: string;
    departments: { id: number; name: string }[];
    identities: {
        id: number;
        platform: string;
        platform_user_id: string;
        platform_username: string;
        platform_display_name: string;
        platform_email: string;
        platform_position: string;
        platform_department: string;
    }[];
}

interface RoleItem {
    id: number;
    name: string;
    display_name: string;
    source: string;
    is_builtin: boolean;
    is_admin: boolean;
    permissions: { code: string; display_name: string }[];
    member_count: number;
}

interface Suggestion {
    id: number;
    source_member_id: string;
    source_name: string;
    source_platform: string;
    target_member_id: string;
    target_name: string;
    match_type: string;
    confidence: number;
}

// ---- 状态 ----

const activeTab = ref("org");

// 组织架构 — 成员列表
const members = ref<MemberItem[]>([]);
const membersTotal = ref(0);
const membersPage = ref(1);
const membersSize = ref(50);
const searchText = ref("");
const filterRole = ref("");
const loadingMembers = ref(false);
const loadingSync = ref(false);
const loadingDedup = ref(false);

// 组织架构 — 当前选中的部门（null = 全部成员）
const selectedDeptId = ref<number | null>(null);

// 通道列表（用于同步选择）
interface ChannelItem {
    name: string;
    display_name: string;
    type: string;
    status: string;
    enabled: boolean;
}
const channels = ref<ChannelItem[]>([]);

// 角色
const roles = ref<RoleItem[]>([]);
const loadingRoles = ref(false);
const selectedRoleIndex = ref(0);
const selectedRole = computed(() => roles.value[selectedRoleIndex.value] || null);
const roleMembers = ref<MemberItem[]>([]);
const loadingRoleMembers = ref(false);

// 权限列表
interface PermissionItem {
    id: number;
    code: string;
    display_name: string;
    source: string;
}
const allPermissions = ref<PermissionItem[]>([]);

// 权限分组
interface PermGroup {
    key: string;
    label: string;
    permissions: PermissionItem[];
}

const CORE_SUBGROUPS: Record<string, string> = {
    contacts: "通讯录",
    members: "成员管理",
    departments: "部门管理",
    plugins: "插件管理",
    skills: "Skill 管理",
    channels: "通道管理",
    settings: "系统设置",
    logs: "日志",
    dashboard: "仪表盘",
    schedules: "计划任务",
    webhooks: "Webhook",
    agents: "Agent",
};

const PLUGIN_DISPLAY_NAMES: Record<string, string> = {
    browser: "浏览器",
    vortflow: "VortFlow 项目管理",
    vortgit: "VortGit 代码仓库",
    zentao: "禅道",
    jenkins: "Jenkins",
    report: "汇报",
    schedule: "计划任务",
};

const groupedPermissions = computed(() => {
    const corePerms = allPermissions.value.filter(p => p.source === "core");
    const pluginPerms = allPermissions.value.filter(p => p.source !== "core");

    const coreGroups: PermGroup[] = [];
    const coreMap = new Map<string, PermissionItem[]>();
    for (const p of corePerms) {
        const prefix = p.code.split(".")[0];
        if (!coreMap.has(prefix)) coreMap.set(prefix, []);
        coreMap.get(prefix)!.push(p);
    }
    for (const [prefix, perms] of coreMap) {
        coreGroups.push({ key: `core.${prefix}`, label: CORE_SUBGROUPS[prefix] || prefix, permissions: perms });
    }

    const pluginGroups: PermGroup[] = [];
    const pluginMap = new Map<string, PermissionItem[]>();
    for (const p of pluginPerms) {
        if (!pluginMap.has(p.source)) pluginMap.set(p.source, []);
        pluginMap.get(p.source)!.push(p);
    }
    for (const [source, perms] of pluginMap) {
        pluginGroups.push({ key: source, label: PLUGIN_DISPLAY_NAMES[source] || source, permissions: perms });
    }

    return { coreGroups, pluginGroups };
});

// 内联编辑状态
const editingPerms = ref<string[] | null>(null);
const savingPermsInline = ref(false);

const canEditPermissions = computed(() => {
    if (!selectedRole.value) return false;
    return !selectedRole.value.is_admin && !selectedRole.value.is_builtin;
});

const activePermCodes = computed(() => {
    if (editingPerms.value !== null) return editingPerms.value;
    if (!selectedRole.value) return [];
    if (selectedRole.value.is_admin) return allPermissions.value.map(p => p.code);
    return selectedRole.value.permissions.map(p => p.code);
});

const hasPermChanges = computed(() => {
    if (editingPerms.value === null || !selectedRole.value) return false;
    const original = new Set(selectedRole.value.permissions.map(p => p.code));
    const current = new Set(editingPerms.value);
    if (original.size !== current.size) return true;
    for (const c of original) { if (!current.has(c)) return true; }
    return false;
});

function isPermSelected(code: string): boolean {
    return activePermCodes.value.includes(code);
}

function isGroupAllSelected(group: PermGroup): boolean {
    return group.permissions.every(p => activePermCodes.value.includes(p.code));
}

function isGroupPartial(group: PermGroup): boolean {
    const sel = group.permissions.filter(p => activePermCodes.value.includes(p.code));
    return sel.length > 0 && sel.length < group.permissions.length;
}

function isSectionAllSelected(groups: PermGroup[]): boolean {
    return groups.length > 0 && groups.every(g => isGroupAllSelected(g));
}

function isSectionPartial(groups: PermGroup[]): boolean {
    const allCodes = groups.flatMap(g => g.permissions.map(p => p.code));
    const selected = allCodes.filter(c => activePermCodes.value.includes(c));
    return selected.length > 0 && selected.length < allCodes.length;
}

function toggleSection(groups: PermGroup[]) {
    if (!canEditPermissions.value) return;
    ensureEditingPerms();
    const allCodes = groups.flatMap(g => g.permissions.map(p => p.code));
    const allSelected = allCodes.every(c => editingPerms.value!.includes(c));
    if (allSelected) {
        const codesSet = new Set(allCodes);
        editingPerms.value = editingPerms.value!.filter(c => !codesSet.has(c));
    } else {
        const existing = new Set(editingPerms.value!);
        for (const c of allCodes) {
            if (!existing.has(c)) editingPerms.value!.push(c);
        }
    }
}

function ensureEditingPerms() {
    if (editingPerms.value === null && selectedRole.value) {
        editingPerms.value = selectedRole.value.permissions.map(p => p.code);
    }
}

function togglePerm(code: string) {
    if (!canEditPermissions.value) return;
    ensureEditingPerms();
    const idx = editingPerms.value!.indexOf(code);
    if (idx >= 0) editingPerms.value!.splice(idx, 1);
    else editingPerms.value!.push(code);
}

function toggleGroup(group: PermGroup) {
    if (!canEditPermissions.value) return;
    ensureEditingPerms();
    const allSelected = group.permissions.every(p => editingPerms.value!.includes(p.code));
    if (allSelected) {
        const codes = new Set(group.permissions.map(p => p.code));
        editingPerms.value = editingPerms.value!.filter(c => !codes.has(c));
    } else {
        const existing = new Set(editingPerms.value!);
        for (const p of group.permissions) {
            if (!existing.has(p.code)) editingPerms.value!.push(p.code);
        }
    }
}

async function savePermissionsInline() {
    if (!selectedRole.value || editingPerms.value === null) return;
    savingPermsInline.value = true;
    try {
        const res: any = await updateRole(selectedRole.value.id, { permissions: editingPerms.value });
        if (res?.success) {
            message.success("权限已保存");
            editingPerms.value = null;
            await loadRoles();
        } else {
            message.error(res?.error || "保存失败");
        }
    } catch { message.error("保存失败"); }
    finally { savingPermsInline.value = false; }
}

function cancelPermEdit() {
    editingPerms.value = null;
}

watch(selectedRoleIndex, () => { editingPerms.value = null; });

// 角色编辑弹窗
const roleEditDialogOpen = ref(false);
const roleEditMode = ref<"create" | "edit">("create");
const roleEditForm = ref({ name: "", display_name: "", permissions: [] as string[] });
const roleEditId = ref<number | null>(null);
const roleEditIsBuiltin = ref(false);
const savingRole = ref(false);

// 匹配建议
const suggestions = ref<Suggestion[]>([]);
const showSuggestions = ref(false);

// 成员详情抽屉
const drawerOpen = ref(false);
const drawerLoading = ref(false);
const currentMember = ref<MemberDetail | null>(null);
const editForm = ref({ name: "", email: "", phone: "", position: "" });
const savingEdit = ref(false);

// 角色分配弹窗
const roleDialogOpen = ref(false);
const roleDialogMember = ref<MemberItem | null>(null);
const roleDialogLoading = ref(false);

// 批量选择
const selectedIds = ref<string[]>([]);

// 批量角色弹窗
const batchRoleDialogOpen = ref(false);
const batchRoleAction = ref<"assign" | "remove">("assign");

// 批量部门弹窗
const batchDeptDialogOpen = ref(false);
const batchDeptAction = ref<"assign" | "remove">("assign");

const rowSelection = computed(() => ({
    selectedRowKeys: selectedIds.value,
    onChange: (keys: (string | number)[]) => {
        selectedIds.value = keys as string[];
    },
}));

// 组织架构 — 部门树
const deptTree = ref<DeptNode[]>([]);
const loadingDepts = ref(false);
const expandedDeptIds = ref<Set<number>>(new Set());
const selectedDept = computed(() => {
    function find(nodes: DeptNode[], id: number): DeptNode | null {
        for (const n of nodes) {
            if (n.id === id) return n;
            const found = find(n.children, id);
            if (found) return found;
        }
        return null;
    }
    return selectedDeptId.value ? find(deptTree.value, selectedDeptId.value) : null;
});
const totalMemberCount = computed(() => {
    function sum(nodes: DeptNode[]): number {
        return nodes.reduce((acc, n) => acc + n.member_count + sum(n.children), 0);
    }
    return sum(deptTree.value);
});

// Breadcrumb path from root to selected dept
const deptBreadcrumb = computed(() => {
    if (!selectedDeptId.value) return [];
    const path: DeptNode[] = [];
    function find(nodes: DeptNode[], target: number): boolean {
        for (const n of nodes) {
            path.push(n);
            if (n.id === target) return true;
            if (find(n.children, target)) return true;
            path.pop();
        }
        return false;
    }
    find(deptTree.value, selectedDeptId.value);
    return path;
});

// 部门编辑
const deptDialogOpen = ref(false);
const deptDialogMode = ref<"create" | "edit">("create");
const deptDialogParentId = ref<number | null>(null);
const deptDialogForm = ref({ name: "" });
const deptDialogEditId = ref<number | null>(null);
const savingDept = ref(false);

// 添加成员到部门弹窗
const addMemberDialogOpen = ref(false);
const addMemberSearch = ref("");
const addMemberResults = ref<MemberItem[]>([]);
const addMemberLoading = ref(false);

// 新增成员弹窗
const createMemberDialogOpen = ref(false);
const createMemberForm = ref({
    name: "", email: "", phone: "", position: "", is_account: false,
});
const savingCreateMember = ref(false);

// 向导式创建成员
const wizardOpen = ref(false);

function openCreateMemberDialog() {
    wizardOpen.value = true;
}

async function handleCreateMember() {
    if (!createMemberForm.value.name.trim()) {
        message.error("请输入姓名");
        return;
    }
    savingCreateMember.value = true;
    try {
        const res: any = await createMember(createMemberForm.value);
        if (res?.success) {
            message.success("成员已创建");
            createMemberDialogOpen.value = false;
            await Promise.all([loadMembers(), loadDeptTree()]);
        } else {
            message.error(res?.error || "创建失败");
        }
    } catch { message.error("创建失败"); }
    finally { savingCreateMember.value = false; }
}

// ---- 成员列表 ----

async function loadMembers() {
    loadingMembers.value = true;
    try {
        const params: any = {
            search: searchText.value,
            role: filterRole.value,
            page: membersPage.value,
            size: membersSize.value,
            is_virtual: false,
        };
        if (selectedDeptId.value !== null) {
            params.department_id = selectedDeptId.value;
        }
        const res: any = await getMembers(params);
        members.value = res?.members || [];
        membersTotal.value = res?.total || 0;
    } catch { /* ignore */ }
    finally { loadingMembers.value = false; }
}

async function handleSearch() {
    membersPage.value = 1;
    await loadMembers();
}

async function handleSync(channel?: string) {
    loadingSync.value = true;
    try {
        const res: any = await syncContacts(channel);
        if (res?.success && res.results?.length) {
            const details = res.results.map((r: any) =>
                `${r.platform}: 新建 ${r.created || 0}, 更新 ${r.updated || 0}, 关联 ${r.matched || 0}, 待确认 ${r.pending || 0}`
            ).join("；");
            message.success(`同步完成 — ${details}`);
        } else if (res?.success) {
            message.success("同步完成，无可用通道");
        } else {
            message.error(res?.error || "同步失败");
        }
        await Promise.all([loadMembers(), loadSuggestions(), loadDeptTree()]);
    } catch { message.error("同步失败"); }
    finally { loadingSync.value = false; }
}

async function loadChannels() {
    try {
        const res: any = await getChannels();
        channels.value = (res?.channels || res || []).filter((c: ChannelItem) => c.enabled);
    } catch { /* ignore */ }
}

async function handleDedup() {
    loadingDedup.value = true;
    try {
        const res: any = await dedupContacts();
        if (res?.success) {
            message.success(`去重完成，合并了 ${res.merged || 0} 个重复联系人`);
            await Promise.all([loadMembers(), loadSuggestions()]);
        } else { message.error("去重失败"); }
    } catch { message.error("去重失败"); }
    finally { loadingDedup.value = false; }
}

// ---- 匹配建议 ----

async function loadSuggestions() {
    try {
        const res: any = await getSuggestions();
        suggestions.value = res?.suggestions || [];
    } catch { /* ignore */ }
}

async function handleAccept(id: number) {
    try {
        const res: any = await acceptSuggestion(id);
        if (res?.success) {
            message.success("已合并");
            await Promise.all([loadMembers(), loadSuggestions()]);
        } else { message.error("操作失败"); }
    } catch { message.error("操作失败"); }
}

async function handleReject(id: number) {
    try {
        const res: any = await rejectSuggestion(id);
        if (res?.success) {
            message.success("已忽略");
            await loadSuggestions();
        } else { message.error("操作失败"); }
    } catch { message.error("操作失败"); }
}

// ---- 成员详情抽屉 ----

async function openMemberDrawer(memberId: string) {
    drawerOpen.value = true;
    drawerLoading.value = true;
    try {
        const res: any = await getMember(memberId);
        currentMember.value = res;
        editForm.value = {
            name: res.name || "",
            email: res.email || "",
            phone: res.phone || "",
            position: res.position || "",
        };
    } catch { message.error("加载失败"); }
    finally { drawerLoading.value = false; }
}

async function handleSaveEdit() {
    if (!currentMember.value) return;
    savingEdit.value = true;
    try {
        const res: any = await updateMember(currentMember.value.id, editForm.value);
        if (res?.success) {
            message.success("保存成功");
            await loadMembers();
            await openMemberDrawer(currentMember.value.id);
        } else { message.error(res?.error || "保存失败"); }
    } catch { message.error("保存失败"); }
    finally { savingEdit.value = false; }
}

async function handleToggleAccount(member: MemberItem) {
    try {
        const res: any = await toggleMemberAccount(member.id);
        if (res?.success) {
            message.success(res.is_account ? "已启用登录" : "已禁用登录");
            await loadMembers();
            if (currentMember.value?.id === member.id) {
                await openMemberDrawer(member.id);
            }
        } else { message.error("操作失败"); }
    } catch { message.error("操作失败"); }
}

async function handleResetPassword(memberId: string) {
    try {
        const res: any = await resetMemberPassword(memberId);
        if (res?.success) {
            message.success("密码已重置为默认密码");
            if (currentMember.value?.id === memberId) {
                await openMemberDrawer(memberId);
            }
        } else { message.error("重置失败"); }
    } catch { message.error("重置失败"); }
}

// ---- 角色管理 ----

async function loadRoles() {
    loadingRoles.value = true;
    try {
        const res: any = await getRoles();
        roles.value = res?.roles || [];
        // 加载默认选中角色的成员
        if (roles.value.length) {
            await loadRoleMembers(roles.value[selectedRoleIndex.value]?.name);
        }
    } catch { /* ignore */ }
    finally { loadingRoles.value = false; }
}

async function loadPermissions() {
    try {
        const res: any = await getPermissions();
        allPermissions.value = res?.permissions || [];
    } catch { /* ignore */ }
}

function openCreateRoleDialog() {
    roleEditMode.value = "create";
    roleEditForm.value = { name: "", display_name: "", permissions: [] };
    roleEditId.value = null;
    roleEditIsBuiltin.value = false;
    roleEditDialogOpen.value = true;
}

function openEditRoleDialog(role: RoleItem) {
    roleEditMode.value = "edit";
    roleEditForm.value = {
        name: role.name,
        display_name: role.display_name,
        permissions: role.is_admin ? [] : role.permissions.map(p => p.code),
    };
    roleEditId.value = role.id;
    roleEditIsBuiltin.value = role.is_builtin;
    roleEditDialogOpen.value = true;
}

async function handleSaveRole() {
    if (!roleEditForm.value.display_name.trim()) {
        message.error("请输入角色显示名");
        return;
    }
    savingRole.value = true;
    try {
        if (roleEditMode.value === "create") {
            if (!roleEditForm.value.name.trim()) {
                message.error("请输入角色标识");
                savingRole.value = false;
                return;
            }
            const res: any = await createRole({
                name: roleEditForm.value.name,
                display_name: roleEditForm.value.display_name,
                permissions: roleEditForm.value.permissions,
            });
            if (res?.success) {
                message.success("角色已创建");
                roleEditDialogOpen.value = false;
                await loadRoles();
            } else {
                message.error(res?.error || "创建失败");
            }
        } else {
            if (!roleEditId.value) return;
            const data: any = { display_name: roleEditForm.value.display_name };
            const res: any = await updateRole(roleEditId.value, data);
            if (res?.success) {
                message.success("角色已更新");
                roleEditDialogOpen.value = false;
                await loadRoles();
            } else {
                message.error(res?.error || "更新失败");
            }
        }
    } catch { message.error("操作失败"); }
    finally { savingRole.value = false; }
}

async function handleDeleteRole(role: RoleItem) {
    if (role.is_builtin) {
        message.error("内置角色不可删除");
        return;
    }
    dialog.confirm({
        title: `确定删除角色「${role.display_name}」？该角色下的 ${role.member_count} 个成员将失去此角色。`,
        okType: "danger",
        onOk: async () => {
            const res: any = await deleteRole(role.id);
            if (res?.success) {
                message.success("角色已删除");
                selectedRoleIndex.value = 0;
                await loadRoles();
            } else {
                message.error(res?.error || "删除失败");
                throw new Error("删除失败");
            }
        },
    });
}

function togglePermission(code: string) {
    const idx = roleEditForm.value.permissions.indexOf(code);
    if (idx >= 0) {
        roleEditForm.value.permissions.splice(idx, 1);
    } else {
        roleEditForm.value.permissions.push(code);
    }
}

function isDialogGroupAllSelected(group: PermGroup): boolean {
    return group.permissions.every(p => roleEditForm.value.permissions.includes(p.code));
}

function isDialogGroupPartial(group: PermGroup): boolean {
    const sel = group.permissions.filter(p => roleEditForm.value.permissions.includes(p.code));
    return sel.length > 0 && sel.length < group.permissions.length;
}

function toggleDialogGroup(group: PermGroup) {
    const allSelected = isDialogGroupAllSelected(group);
    if (allSelected) {
        const codes = new Set(group.permissions.map(p => p.code));
        roleEditForm.value.permissions = roleEditForm.value.permissions.filter(c => !codes.has(c));
    } else {
        const existing = new Set(roleEditForm.value.permissions);
        for (const p of group.permissions) {
            if (!existing.has(p.code)) roleEditForm.value.permissions.push(p.code);
        }
    }
}

function isDialogSectionAllSelected(groups: PermGroup[]): boolean {
    return groups.length > 0 && groups.every(g => isDialogGroupAllSelected(g));
}

function isDialogSectionPartial(groups: PermGroup[]): boolean {
    const allCodes = groups.flatMap(g => g.permissions.map(p => p.code));
    const selected = allCodes.filter(c => roleEditForm.value.permissions.includes(c));
    return selected.length > 0 && selected.length < allCodes.length;
}

function toggleDialogSection(groups: PermGroup[]) {
    const allCodes = groups.flatMap(g => g.permissions.map(p => p.code));
    const allSelected = allCodes.every(c => roleEditForm.value.permissions.includes(c));
    if (allSelected) {
        const codesSet = new Set(allCodes);
        roleEditForm.value.permissions = roleEditForm.value.permissions.filter(c => !codesSet.has(c));
    } else {
        const existing = new Set(roleEditForm.value.permissions);
        for (const c of allCodes) {
            if (!existing.has(c)) roleEditForm.value.permissions.push(c);
        }
    }
}

async function loadRoleMembers(roleName?: string) {
    if (!roleName) return;
    loadingRoleMembers.value = true;
    try {
        const res: any = await getMembers({ role: roleName, size: 999 });
        roleMembers.value = res?.members || [];
    } catch { roleMembers.value = []; }
    finally { loadingRoleMembers.value = false; }
}

async function handleAssignRole(memberId: string, roleName: string) {
    try {
        const res: any = await assignMemberRole(memberId, roleName);
        if (res?.success) {
            message.success("角色已分配");
            await loadMembers();
            if (currentMember.value?.id === memberId) {
                await openMemberDrawer(memberId);
            }
        } else { message.error("分配失败"); }
    } catch { message.error("分配失败"); }
}

async function handleRemoveRole(memberId: string, roleName: string) {
    try {
        const res: any = await removeMemberRole(memberId, roleName);
        if (res?.success) {
            message.success("角色已移除");
            await loadMembers();
            if (currentMember.value?.id === memberId) {
                await openMemberDrawer(memberId);
            }
        } else { message.error("移除失败"); }
    } catch { message.error("移除失败"); }
}

// 角色分配弹窗
function openRoleDialog(member: MemberItem) {
    roleDialogMember.value = member;
    roleDialogOpen.value = true;
}

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

// ---- 删除 ----

async function handleDelete(memberId: string, memberName: string) {
    dialog.confirm({
        title: `确定删除成员「${memberName}」？此操作不可恢复。`,
        okType: "danger",
        onOk: async () => {
            const res: any = await deleteMember(memberId);
            if (res?.success) {
                message.success("已删除");
                drawerOpen.value = false;
                selectedIds.value = selectedIds.value.filter(id => id !== memberId);
                await loadMembers();
            } else {
                message.error(res?.error || "删除失败");
                throw new Error("删除失败");
            }
        },
    });
}

// ---- 批量操作 ----

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

async function handleBatchEnableAccount() {
    if (!selectedIds.value.length) return;
    try {
        const res: any = await batchEnableAccount(selectedIds.value);
        if (res?.success) {
            message.success(`已启用 ${res.count} 个账号`);
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

// ---- 部门管理 ----

// ---- 部门管理 ----

// 详情抽屉：添加/移除部门
const drawerDeptDialogOpen = ref(false);

async function handleAddDeptToMember(deptId: number) {
    if (!currentMember.value) return;
    try {
        const res: any = await addDepartmentMember(deptId, currentMember.value.id);
        if (res?.success) {
            message.success("已添加到部门");
            await Promise.all([openMemberDrawer(currentMember.value.id), loadMembers()]);
        } else { message.error("添加失败（可能已在该部门）"); }
    } catch { message.error("添加失败"); }
}

async function handleRemoveDeptFromMember(deptId: number) {
    if (!currentMember.value) return;
    try {
        const res: any = await removeDepartmentMember(deptId, currentMember.value.id);
        if (res?.success) {
            message.success("已从部门移除");
            await Promise.all([openMemberDrawer(currentMember.value.id), loadMembers()]);
        } else { message.error("移除失败"); }
    } catch { message.error("移除失败"); }
}

async function loadDeptTree() {
    loadingDepts.value = true;
    try {
        const res: any = await getDepartmentTree();
        deptTree.value = res?.departments || [];
        const ids = new Set<number>();
        function collect(nodes: DeptNode[]) {
            for (const n of nodes) {
                if (n.children.length) {
                    ids.add(n.id);
                    collect(n.children);
                }
            }
        }
        collect(deptTree.value);
        expandedDeptIds.value = ids;
    } catch { /* ignore */ }
    finally { loadingDepts.value = false; }
}

function handleSelectDept(deptId: number | null) {
    selectedDeptId.value = deptId;
    membersPage.value = 1;
    loadMembers();
}

function handleToggleDeptExpand(deptId: number) {
    const next = new Set(expandedDeptIds.value);
    if (next.has(deptId)) next.delete(deptId);
    else next.add(deptId);
    expandedDeptIds.value = next;
}

function openCreateDeptDialog(parentId: number | null = null) {
    deptDialogMode.value = "create";
    deptDialogParentId.value = parentId;
    deptDialogForm.value = { name: "" };
    deptDialogEditId.value = null;
    deptDialogOpen.value = true;
}

function openEditDeptDialog(dept: DeptNode) {
    deptDialogMode.value = "edit";
    deptDialogForm.value = { name: dept.name };
    deptDialogEditId.value = dept.id;
    deptDialogParentId.value = dept.parent_id;
    deptDialogOpen.value = true;
}

async function handleSaveDept() {
    if (!deptDialogForm.value.name.trim()) return;
    savingDept.value = true;
    try {
        if (deptDialogMode.value === "create") {
            const res: any = await createDepartment(deptDialogForm.value.name, deptDialogParentId.value);
            if (res?.success) {
                message.success("部门已创建");
                deptDialogOpen.value = false;
                await loadDeptTree();
            } else { message.error(res?.error || "创建失败"); }
        } else {
            if (!deptDialogEditId.value) return;
            const res: any = await updateDepartment(deptDialogEditId.value, { name: deptDialogForm.value.name });
            if (res?.success) {
                message.success("部门已更新");
                deptDialogOpen.value = false;
                await loadDeptTree();
            } else { message.error("更新失败"); }
        }
    } catch { message.error("操作失败"); }
    finally { savingDept.value = false; }
}

async function handleDeleteDept(deptId: number, deptName: string) {
    dialog.confirm({
        title: `确定删除部门「${deptName}」？子部门将上移到父级。`,
        okType: "danger",
        onOk: async () => {
            const res: any = await deleteDepartment(deptId);
            if (res?.success) {
                message.success("部门已删除");
                if (selectedDeptId.value === deptId) {
                    selectedDeptId.value = null;
                }
                await Promise.all([loadDeptTree(), loadMembers()]);
            } else {
                message.error("删除失败");
                throw new Error("删除失败");
            }
        },
    });
}

async function handleSearchAddMember() {
    if (!addMemberSearch.value.trim()) return;
    addMemberLoading.value = true;
    try {
        const res: any = await getMembers({ search: addMemberSearch.value, size: 20 });
        addMemberResults.value = res?.members || [];
    } catch { addMemberResults.value = []; }
    finally { addMemberLoading.value = false; }
}

async function handleAddMemberToDept(memberId: string) {
    if (!selectedDeptId.value) return;
    try {
        const res: any = await addDepartmentMember(selectedDeptId.value, memberId);
        if (res?.success) {
            message.success("已添加");
            await Promise.all([loadMembers(), loadDeptTree()]);
        } else { message.error("添加失败（可能已在该部门）"); }
    } catch { message.error("添加失败"); }
}

async function handleRemoveMemberFromDept(memberId: string) {
    if (!selectedDeptId.value) return;
    try {
        const res: any = await removeDepartmentMember(selectedDeptId.value, memberId);
        if (res?.success) {
            message.success("已从部门移除");
            await Promise.all([loadMembers(), loadDeptTree()]);
        } else { message.error("移除失败"); }
    } catch { message.error("移除失败"); }
}

// ---- 企业日历 ----

interface CalendarEntry {
    id: number;
    date: string;
    day_type: string;
    name: string;
    year: number;
}

interface WorkSettingsData {
    timezone: string;
    work_start: string;
    work_end: string;
    work_days: string;
    lunch_start: string;
    lunch_end: string;
}

const calendarEntries = ref<CalendarEntry[]>([]);
const loadingCalendar = ref(false);
const calendarYear = ref(new Date().getFullYear());
const syncingHolidays = ref(false);
const workSettings = ref<WorkSettingsData | null>(null);

const calendarDialogOpen = ref(false);
const calendarForm = ref({ date: "", day_type: "holiday", name: "" });
const savingCalendar = ref(false);

const editingWorkSettings = ref(false);
const savingWorkSettings = ref(false);
const workSettingsForm = ref({
    timezone: "",
    work_start: "",
    work_end: "",
    lunch_start: "",
    lunch_end: "",
    work_days: [] as number[],
});

const weekDayOptions = [
    { label: "周一", value: 1 },
    { label: "周二", value: 2 },
    { label: "周三", value: 3 },
    { label: "周四", value: 4 },
    { label: "周五", value: 5 },
    { label: "周六", value: 6 },
    { label: "周日", value: 7 },
];

const dayTypeOptions = [
    { label: "放假", value: "holiday" },
    { label: "调休上班", value: "workday" },
];
const dayTypeLabel = (val: string) => dayTypeOptions.find(o => o.value === val)?.label || val;
const dayTypeColor = (val: string) => val === "holiday" ? "red" : "blue";

async function loadCalendar() {
    loadingCalendar.value = true;
    try {
        const res: any = await getOrgCalendar(calendarYear.value);
        calendarEntries.value = res?.entries || [];
    } catch { /* ignore */ }
    finally { loadingCalendar.value = false; }
}

async function loadWorkSettings() {
    try {
        const res: any = await getWorkSettings();
        workSettings.value = res;
    } catch { /* ignore */ }
}

function startEditWorkSettings() {
    if (!workSettings.value) return;
    workSettingsForm.value = {
        timezone: workSettings.value.timezone,
        work_start: workSettings.value.work_start,
        work_end: workSettings.value.work_end,
        lunch_start: workSettings.value.lunch_start,
        lunch_end: workSettings.value.lunch_end,
        work_days: workSettings.value.work_days.split(",").map(Number),
    };
    editingWorkSettings.value = true;
}

function cancelEditWorkSettings() {
    editingWorkSettings.value = false;
}

async function handleSaveWorkSettings() {
    savingWorkSettings.value = true;
    try {
        const res: any = await updateWorkSettings({
            timezone: workSettingsForm.value.timezone,
            work_start: workSettingsForm.value.work_start,
            work_end: workSettingsForm.value.work_end,
            lunch_start: workSettingsForm.value.lunch_start,
            lunch_end: workSettingsForm.value.lunch_end,
            work_days: workSettingsForm.value.work_days.sort((a, b) => a - b).join(","),
        });
        if (res?.success) {
            message.success("工时设置已保存");
            editingWorkSettings.value = false;
            await loadWorkSettings();
        } else { message.error(res?.error || "保存失败"); }
    } catch { message.error("保存失败"); }
    finally { savingWorkSettings.value = false; }
}

async function handleSyncHolidays() {
    syncingHolidays.value = true;
    try {
        const res: any = await syncHolidays(calendarYear.value);
        if (res?.success) {
            message.success(`同步完成：新增 ${res.created} 条，跳过 ${res.skipped} 条`);
            await loadCalendar();
        } else { message.error(res?.error || "同步失败"); }
    } catch { message.error("同步失败"); }
    finally { syncingHolidays.value = false; }
}

function openCalendarDialog() {
    calendarForm.value = { date: "", day_type: "holiday", name: "" };
    calendarDialogOpen.value = true;
}

async function handleSaveCalendar() {
    if (!calendarForm.value.date) {
        message.error("请选择日期");
        return;
    }
    savingCalendar.value = true;
    try {
        const res: any = await createOrgCalendarEntry(calendarForm.value);
        if (res?.success) {
            message.success("已添加");
            calendarDialogOpen.value = false;
            await loadCalendar();
        } else { message.error(res?.error || "添加失败"); }
    } catch { message.error("添加失败"); }
    finally { savingCalendar.value = false; }
}

async function handleDeleteCalendar(id: number) {
    try {
        const res: any = await deleteOrgCalendarEntry(id);
        if (res?.success) {
            message.success("已删除");
            await loadCalendar();
        } else { message.error("删除失败"); }
    } catch { message.error("删除失败"); }
}

// ---- 头像工具 ----

const AVATAR_COLORS = [
    'bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500',
    'bg-pink-500', 'bg-teal-500', 'bg-indigo-500', 'bg-red-400',
    'bg-cyan-500', 'bg-amber-500',
];

function getInitial(name: string): string {
    if (!name) return '?';
    const trimmed = name.trim();
    // 英文名取首字母大写，中文取第一个字
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

// 角色显示名（优先后端配置，其次内置映射，最后回退英文标识）
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

// ---- 初始化 ----

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
                                            <div class="flex items-center gap-1">
                                                <span class="text-blue-600 cursor-pointer hover:underline" @click="openMemberDrawer(row.id)">{{ row.name }}</span>
                                            </div>
                                        </div>
                                    </template>
                                </VortTableColumn>
                                <VortTableColumn label="职务" prop="position" :width="140">
                                    <template #default="{ row }">
                                        <span class="text-sm text-gray-600">{{ row.position || '-' }}</span>
                                    </template>
                                </VortTableColumn>
                                <VortTableColumn label="部门" :width="180">
                                    <template #default="{ row }">
                                        <span v-if="row.departments?.length" class="text-sm text-gray-600">{{ row.departments.join('、') }}</span>
                                        <span v-else class="text-sm text-gray-400">-</span>
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
                                {{ currentMember.has_password ? '已设置独立密码' : '使用默认密码' }}
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
    </div>
</template>

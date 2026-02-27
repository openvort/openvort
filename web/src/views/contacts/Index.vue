<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import {
    getMembers, getMember, updateMember, resetMemberPassword,
    toggleMemberAccount, assignMemberRole, removeMemberRole,
    deleteMember, batchDeleteMembers, batchEnableAccount,
    batchDisableAccount, batchAssignRole, batchRemoveRole,
    batchAssignDept, batchRemoveDept,
    getRoles, getPermissions, createRole, updateRole, deleteRole,
    syncContacts, getSuggestions,
    acceptSuggestion, rejectSuggestion, dedupContacts,
    getDepartmentTree, getDepartmentMembers, createDepartment,
    updateDepartment, deleteDepartment, addDepartmentMember,
    removeDepartmentMember, getChannels
} from "@/api";
import {
    RefreshCw, Search, Shield, UserCheck, UserX, Key,
    AlertTriangle, Check, X, Link, Unlink, Lock, Trash2,
    ChevronRight, ChevronDown, FolderTree, Plus, Pencil, UserPlus, UserMinus,
    Download
} from "lucide-vue-next";
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";

// ---- 类型 ----

interface MemberItem {
    id: string;
    name: string;
    email: string;
    phone: string;
    status: string;
    is_account: boolean;
    has_password: boolean;
    roles: string[];
    platform_accounts: Record<string, string>;
    created_at: string;
}

interface MemberDetail extends MemberItem {
    avatar_url: string;
    permissions: string[];
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

const activeTab = ref("members");

// 成员列表
const members = ref<MemberItem[]>([]);
const membersTotal = ref(0);
const membersPage = ref(1);
const membersSize = ref(50);
const searchText = ref("");
const filterRole = ref("");
const loadingMembers = ref(false);
const loadingSync = ref(false);
const loadingDedup = ref(false);

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
const editForm = ref({ name: "", email: "", phone: "" });
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

// 部门管理
interface DeptNode {
    id: number;
    name: string;
    parent_id: number | null;
    platform: string;
    platform_dept_id: string;
    order: number;
    member_count: number;
    children: DeptNode[];
}

interface DeptMember {
    id: string;
    name: string;
    email: string;
    phone: string;
    is_primary: boolean;
}

const deptTree = ref<DeptNode[]>([]);
const loadingDepts = ref(false);
const expandedDeptIds = ref<Set<number>>(new Set());
const selectedDeptId = ref<number | null>(null);
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
const deptMembers = ref<DeptMember[]>([]);
const loadingDeptMembers = ref(false);

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

// ---- 成员列表 ----

async function loadMembers() {
    loadingMembers.value = true;
    try {
        const res: any = await getMembers({
            search: searchText.value,
            role: filterRole.value,
            page: membersPage.value,
            size: membersSize.value,
        });
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
            if (!roleEditIsBuiltin.value) {
                data.permissions = roleEditForm.value.permissions;
            }
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
    roleDialogLoading.value = true;
    const member = roleDialogMember.value;
    const hasRole = member.roles.includes(roleName);
    if (hasRole) {
        await handleRemoveRole(member.id, roleName);
    } else {
        await handleAssignRole(member.id, roleName);
    }
    // 刷新 member 数据
    const updated = members.value.find(m => m.id === member.id);
    if (updated) roleDialogMember.value = updated;
    roleDialogLoading.value = false;
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
        // 默认展开所有节点
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
        // 默认选中第一个部门
        if (deptTree.value.length && !selectedDeptId.value) {
            selectDept(deptTree.value[0].id);
        }
    } catch { /* ignore */ }
    finally { loadingDepts.value = false; }
}

async function loadDeptMembers(deptId: number) {
    loadingDeptMembers.value = true;
    try {
        const res: any = await getDepartmentMembers(deptId);
        deptMembers.value = res?.members || [];
    } catch { deptMembers.value = []; }
    finally { loadingDeptMembers.value = false; }
}

function selectDept(deptId: number) {
    selectedDeptId.value = deptId;
    loadDeptMembers(deptId);
}

function toggleDeptExpand(deptId: number) {
    if (expandedDeptIds.value.has(deptId)) {
        expandedDeptIds.value.delete(deptId);
    } else {
        expandedDeptIds.value.add(deptId);
    }
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
                    deptMembers.value = [];
                }
                await loadDeptTree();
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
            await Promise.all([loadDeptMembers(selectedDeptId.value!), loadDeptTree()]);
        } else { message.error("添加失败（可能已在该部门）"); }
    } catch { message.error("添加失败"); }
}

async function handleRemoveMemberFromDept(memberId: string) {
    if (!selectedDeptId.value) return;
    try {
        const res: any = await removeDepartmentMember(selectedDeptId.value, memberId);
        if (res?.success) {
            message.success("已移除");
            await Promise.all([loadDeptMembers(selectedDeptId.value!), loadDeptTree()]);
        } else { message.error("移除失败"); }
    } catch { message.error("移除失败"); }
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

// ---- 初始化 ----

onMounted(() => {
    loadMembers();
    loadSuggestions();
    loadRoles();
    loadPermissions();
    loadDeptTree();
    loadChannels();
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
                <VortTabPane tab-key="members" tab="成员列表">
                    <!-- 工具栏 -->
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-2">
                            <VortInputSearch
                                v-model="searchText"
                                placeholder="搜索姓名、邮箱、手机"
                                style="width: 224px"
                                @search="handleSearch"
                                @press-enter="handleSearch"
                            />
                            <VortSelect
                                v-model="filterRole"
                                placeholder="全部角色"
                                allow-clear
                                style="width: 160px"
                                @change="handleSearch"
                            >
                                <VortSelectOption v-for="r in roles" :key="r.name" :value="r.name">{{ r.display_name }}</VortSelectOption>
                            </VortSelect>
                        </div>
                        <div class="flex items-center gap-2">
                            <VortButton :loading="loadingDedup" @click="handleDedup">
                                <Search :size="14" class="mr-1" /> 去重扫描
                            </VortButton>
                            <VortDropdown trigger="click">
                                <VortButton variant="primary" :loading="loadingSync">
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
                        </div>
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
                                    <span class="text-blue-600 cursor-pointer hover:underline" @click="openMemberDrawer(row.id)">{{ row.name }}</span>
                                </div>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="邮箱" prop="email" />
                        <VortTableColumn label="角色" prop="roles">
                            <template #default="{ row }">
                                <VortTag v-for="role in (row.roles || [])" :key="role" class="mr-1"
                                    :color="role === 'admin' ? 'red' : role === 'manager' ? 'orange' : 'default'">
                                    {{ role }}
                                </VortTag>
                                <span v-if="!row.roles?.length" class="text-gray-400 text-sm">无角色</span>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="平台绑定" prop="platform_accounts">
                            <template #default="{ row }">
                                <template v-if="row.platform_accounts && Object.keys(row.platform_accounts).length">
                                    <VortTag v-for="(_account, platform) in row.platform_accounts" :key="platform" color="blue" class="mr-1">
                                        <Link :size="12" class="mr-1 inline" /> {{ platform }}
                                    </VortTag>
                                </template>
                                <span v-else class="text-gray-400 text-sm flex items-center">
                                    <Unlink :size="12" class="mr-1" /> 未绑定
                                </span>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="账号状态" prop="is_account" :width="100">
                            <template #default="{ row }">
                                <VortTag v-if="row.is_account" color="green">可登录</VortTag>
                                <VortTag v-else>纯联系人</VortTag>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="操作" :width="240">
                            <template #default="{ row }">
                                <TableActions>
                                    <TableActionsItem @click="openMemberDrawer(row.id)">编辑</TableActionsItem>
                                    <TableActionsItem @click="openRoleDialog(row)">角色</TableActionsItem>
                                    <TableActionsItem @click="handleToggleAccount(row)">
                                        {{ row.is_account ? '禁用' : '启用' }}
                                    </TableActionsItem>
                                    <TableActionsItem danger @click="handleDelete(row.id, row.name)">删除</TableActionsItem>
                                </TableActions>
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

                                <!-- 权限列表 -->
                                <div class="mb-6">
                                    <div class="text-sm font-medium text-gray-600 mb-2">权限</div>
                                    <div class="flex flex-wrap gap-2">
                                        <VortTag
                                            v-for="perm in selectedRole.permissions" :key="perm.code"
                                            :color="perm.code === '*' ? 'red' : 'blue'"
                                        >
                                            {{ perm.display_name || perm.code }}
                                        </VortTag>
                                        <span v-if="!selectedRole.permissions.length" class="text-gray-400 text-sm">无权限</span>
                                    </div>
                                </div>

                                <!-- 所有已注册权限一览 -->
                                <div class="mb-6">
                                    <div class="text-sm font-medium text-gray-600 mb-2">所有已注册权限</div>
                                    <div class="flex flex-wrap gap-2">
                                        <VortTag v-for="p in allPermissions" :key="p.code" color="default" size="small">
                                            {{ p.display_name }} <span class="text-gray-400 ml-1">({{ p.code }})</span>
                                        </VortTag>
                                        <span v-if="!allPermissions.length" class="text-gray-400 text-sm">暂无权限</span>
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
                                                v-if="roleMembers.length > ROLE_MEMBER_DISPLAY_LIMIT"
                                                class="text-gray-400 text-sm leading-6"
                                            >等其他 {{ roleMembers.length - ROLE_MEMBER_DISPLAY_LIMIT }} 名成员</span>
                                            <span v-if="!roleMembers.length && !loadingRoleMembers" class="text-gray-400 text-sm">暂无成员</span>
                                        </div>
                                    </VortSpin>
                                </div>
                            </template>
                            <div v-else class="text-gray-400 text-sm text-center py-16">请选择一个角色查看详情</div>
                        </div>
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="departments" tab="部门管理">
                    <div class="flex gap-6" style="min-height: 400px;">
                        <!-- 左侧：部门树 -->
                        <div class="w-72 flex-shrink-0">
                            <div class="flex items-center justify-between mb-3">
                                <div class="text-sm font-medium text-gray-600">组织架构</div>
                                <div class="flex items-center gap-2">
                                    <VortDropdown trigger="click">
                                        <VortButton size="small" :loading="loadingSync">
                                            <RefreshCw :size="14" class="mr-1" /> 同步
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
                                        <Plus :size="14" class="mr-1" /> 新建部门
                                    </VortButton>
                                </div>
                            </div>
                            <VortSpin :spinning="loadingDepts">
                                <div v-if="deptTree.length" class="space-y-0.5">
                                    <template v-for="node in deptTree" :key="node.id">
                                        <div class="dept-tree-node" :data-dept-id="node.id">
                                            <div
                                                class="flex items-center px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm"
                                                :class="selectedDeptId === node.id ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50 text-gray-700'"
                                                @click="selectDept(node.id)"
                                            >
                                                <span
                                                    v-if="node.children.length"
                                                    class="mr-1 cursor-pointer"
                                                    @click.stop="toggleDeptExpand(node.id)"
                                                >
                                                    <ChevronDown v-if="expandedDeptIds.has(node.id)" :size="14" />
                                                    <ChevronRight v-else :size="14" />
                                                </span>
                                                <span v-else class="mr-1 w-3.5" />
                                                <FolderTree :size="14" class="mr-2 text-gray-400" />
                                                <span class="flex-1 truncate">{{ node.name }}</span>
                                                <span class="text-xs text-gray-400 ml-1">{{ node.member_count }}</span>
                                            </div>
                                            <!-- 子部门递归（最多3层，用缩进） -->
                                            <div v-if="node.children.length && expandedDeptIds.has(node.id)" class="pl-4">
                                                <template v-for="child in node.children" :key="child.id">
                                                    <div
                                                        class="flex items-center px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm"
                                                        :class="selectedDeptId === child.id ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50 text-gray-700'"
                                                        @click="selectDept(child.id)"
                                                    >
                                                        <span
                                                            v-if="child.children.length"
                                                            class="mr-1 cursor-pointer"
                                                            @click.stop="toggleDeptExpand(child.id)"
                                                        >
                                                            <ChevronDown v-if="expandedDeptIds.has(child.id)" :size="14" />
                                                            <ChevronRight v-else :size="14" />
                                                        </span>
                                                        <span v-else class="mr-1 w-3.5" />
                                                        <FolderTree :size="14" class="mr-2 text-gray-400" />
                                                        <span class="flex-1 truncate">{{ child.name }}</span>
                                                        <span class="text-xs text-gray-400 ml-1">{{ child.member_count }}</span>
                                                    </div>
                                                    <!-- 第三层 -->
                                                    <div v-if="child.children.length && expandedDeptIds.has(child.id)" class="pl-4">
                                                        <div
                                                            v-for="leaf in child.children" :key="leaf.id"
                                                            class="flex items-center px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm"
                                                            :class="selectedDeptId === leaf.id ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50 text-gray-700'"
                                                            @click="selectDept(leaf.id)"
                                                        >
                                                            <span class="mr-1 w-3.5" />
                                                            <FolderTree :size="14" class="mr-2 text-gray-400" />
                                                            <span class="flex-1 truncate">{{ leaf.name }}</span>
                                                            <span class="text-xs text-gray-400 ml-1">{{ leaf.member_count }}</span>
                                                        </div>
                                                    </div>
                                                </template>
                                            </div>
                                        </div>
                                    </template>
                                </div>
                                <div v-else class="text-gray-400 text-sm text-center py-8">
                                    暂无部门，同步联系人后自动创建
                                </div>
                            </VortSpin>
                        </div>

                        <!-- 右侧：选中部门详情 + 成员 -->
                        <div class="flex-1 min-w-0">
                            <template v-if="selectedDept">
                                <div class="flex items-center justify-between mb-4">
                                    <div>
                                        <h4 class="text-base font-medium text-gray-800">{{ selectedDept.name }}</h4>
                                        <div class="text-xs text-gray-400 mt-1">
                                            <VortTag v-if="selectedDept.platform !== 'manual'" color="blue" size="small">{{ selectedDept.platform }}</VortTag>
                                            <VortTag v-else size="small">手动创建</VortTag>
                                            <span class="ml-2">{{ selectedDept.member_count }} 人</span>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2">
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
                                    </div>
                                </div>

                                <!-- 部门成员列表 -->
                                <VortSpin :spinning="loadingDeptMembers">
                                    <div v-if="deptMembers.length" class="space-y-2">
                                        <div
                                            v-for="m in deptMembers" :key="m.id"
                                            class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100 hover:bg-gray-50"
                                        >
                                            <div class="flex items-center gap-3">
                                                <span
                                                    class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-medium flex-shrink-0"
                                                    :class="getAvatarColor(m.name)"
                                                >{{ getInitial(m.name) }}</span>
                                                <span class="text-sm font-medium text-gray-800">{{ m.name }}</span>
                                                <span v-if="m.email" class="text-xs text-gray-400">{{ m.email }}</span>
                                                <VortTag v-if="m.is_primary" color="blue" size="small">主部门</VortTag>
                                            </div>
                                            <VortButton size="small" @click="handleRemoveMemberFromDept(m.id)">
                                                <UserMinus :size="12" class="mr-1" /> 移除
                                            </VortButton>
                                        </div>
                                    </div>
                                    <div v-else class="text-gray-400 text-sm text-center py-8">该部门暂无成员</div>
                                </VortSpin>
                            </template>
                            <div v-else class="text-gray-400 text-sm text-center py-16">请选择一个部门查看详情</div>
                        </div>
                    </div>
                </VortTabPane>
            </VortTabs>
        </div>

        <!-- 成员详情抽屉 -->
        <VortDrawer :open="drawerOpen" title="成员详情" :width="480" @update:open="drawerOpen = $event">
            <template v-if="drawerLoading">
                <div class="flex items-center justify-center py-16 text-gray-400">加载中...</div>
            </template>
            <template v-else-if="currentMember">
                <div class="space-y-6">
                    <!-- 基本信息编辑 -->
                    <div>
                        <h4 class="text-sm font-medium text-gray-600 mb-3">基本信息</h4>
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
                            <VortFormItem>
                                <VortButton variant="primary" size="small" :loading="savingEdit" @click="handleSaveEdit">保存</VortButton>
                            </VortFormItem>
                        </VortForm>
                    </div>

                    <!-- 部门 -->
                    <div>
                        <h4 class="text-sm font-medium text-gray-600 mb-3">部门</h4>
                        <div class="flex flex-wrap gap-2">
                            <VortTag
                                v-for="dept in currentMember.departments" :key="dept.id"
                                closable
                                @close="handleRemoveDeptFromMember(dept.id)"
                            >
                                <FolderTree :size="12" class="mr-1" /> {{ dept.name }}
                            </VortTag>
                            <span v-if="!currentMember.departments?.length" class="text-gray-400 text-sm">无部门</span>
                        </div>
                        <div class="mt-2">
                            <VortButton size="small" @click="drawerDeptDialogOpen = true">
                                <Plus :size="12" class="mr-1" /> 添加到部门
                            </VortButton>
                        </div>
                    </div>

                    <!-- 角色 -->
                    <div>
                        <h4 class="text-sm font-medium text-gray-600 mb-3">角色</h4>
                        <div class="flex flex-wrap gap-2">
                            <VortTag
                                v-for="role in currentMember.roles" :key="role"
                                :color="role === 'admin' ? 'red' : role === 'manager' ? 'orange' : 'default'"
                                closable
                                @close="handleRemoveRole(currentMember!.id, role)"
                            >
                                {{ role }}
                            </VortTag>
                            <span v-if="!currentMember.roles.length" class="text-gray-400 text-sm">无角色</span>
                        </div>
                        <div class="mt-2 flex flex-wrap gap-1">
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

                    <!-- 账号操作 -->
                    <div>
                        <h4 class="text-sm font-medium text-gray-600 mb-3">账号</h4>
                        <div class="flex items-center gap-3">
                            <VortTag v-if="currentMember.is_account" color="green">
                                <UserCheck :size="12" class="mr-1" /> 可登录
                            </VortTag>
                            <VortTag v-else>
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

                    <!-- 平台身份 -->
                    <div>
                        <h4 class="text-sm font-medium text-gray-600 mb-3">平台身份</h4>
                        <div v-if="currentMember.identities.length" class="space-y-2">
                            <div v-for="ident in currentMember.identities" :key="ident.id"
                                class="bg-gray-50 rounded-lg px-4 py-3 text-sm">
                                <div class="flex items-center gap-2 mb-1">
                                    <VortTag color="blue" size="small">{{ ident.platform }}</VortTag>
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
            </template>
        </VortDrawer>

        <!-- 角色分配弹窗 -->
        <VortDialog :open="roleDialogOpen" title="角色管理" @update:open="roleDialogOpen = $event">
            <template v-if="roleDialogMember">
                <div class="mb-3 text-sm text-gray-600">
                    为 <span class="font-medium text-gray-800">{{ roleDialogMember.name }}</span> 分配角色
                </div>
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
                        <Check v-if="roleDialogMember.roles.includes(r.name)" :size="16" class="text-blue-600" />
                    </div>
                </div>
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
        <VortDialog :open="batchDeptDialogOpen" :title="batchDeptAction === 'assign' ? '批量分配部门' : '批量移除部门'" @update:open="batchDeptDialogOpen = $event">
            <div class="mb-3 text-sm text-gray-600">
                选择要{{ batchDeptAction === 'assign' ? '分配' : '移除' }}的部门（影响 {{ selectedIds.length }} 人）
            </div>
            <div class="space-y-2 max-h-80 overflow-y-auto">
                <template v-for="node in deptTree" :key="node.id">
                    <div
                        class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer"
                        @click="handleBatchDeptSelect(node.id)"
                    >
                        <div class="flex items-center gap-2">
                            <FolderTree :size="14" class="text-gray-400" />
                            <span class="text-sm font-medium text-gray-700">{{ node.name }}</span>
                        </div>
                        <span class="text-xs text-gray-400">{{ node.member_count }} 人</span>
                    </div>
                    <template v-if="node.children.length">
                        <div
                            v-for="child in node.children" :key="child.id"
                            class="flex items-center justify-between px-4 py-3 pl-10 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer"
                            @click="handleBatchDeptSelect(child.id)"
                        >
                            <div class="flex items-center gap-2">
                                <FolderTree :size="14" class="text-gray-400" />
                                <span class="text-sm font-medium text-gray-700">{{ child.name }}</span>
                            </div>
                            <span class="text-xs text-gray-400">{{ child.member_count }} 人</span>
                        </div>
                    </template>
                </template>
                <div v-if="!deptTree.length" class="text-gray-400 text-sm text-center py-4">暂无部门</div>
            </div>
        </VortDialog>

        <!-- 详情抽屉：添加到部门弹窗 -->
        <VortDialog :open="drawerDeptDialogOpen" title="添加到部门" :footer="false" @update:open="drawerDeptDialogOpen = $event">
            <div class="space-y-2 max-h-80 overflow-y-auto">
                <template v-for="node in deptTree" :key="node.id">
                    <div
                        class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer"
                        @click="handleAddDeptToMember(node.id); drawerDeptDialogOpen = false;"
                    >
                        <div class="flex items-center gap-2">
                            <FolderTree :size="14" class="text-gray-400" />
                            <span class="text-sm font-medium text-gray-700">{{ node.name }}</span>
                        </div>
                        <span class="text-xs text-gray-400">{{ node.member_count }} 人</span>
                    </div>
                    <template v-if="node.children.length">
                        <div
                            v-for="child in node.children" :key="child.id"
                            class="flex items-center justify-between px-4 py-3 pl-10 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer"
                            @click="handleAddDeptToMember(child.id); drawerDeptDialogOpen = false;"
                        >
                            <div class="flex items-center gap-2">
                                <FolderTree :size="14" class="text-gray-400" />
                                <span class="text-sm font-medium text-gray-700">{{ child.name }}</span>
                            </div>
                            <span class="text-xs text-gray-400">{{ child.member_count }} 人</span>
                        </div>
                    </template>
                </template>
                <div v-if="!deptTree.length" class="text-gray-400 text-sm text-center py-4">暂无部门</div>
            </div>
        </VortDialog>

        <!-- 角色编辑弹窗 -->
        <VortDialog
            :open="roleEditDialogOpen"
            :title="roleEditMode === 'create' ? '新建角色' : '编辑角色'"
            :ok-text="roleEditMode === 'create' ? '创建' : '保存'"
            :confirm-loading="savingRole"
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
                <div v-if="!roleEditIsBuiltin || roleEditMode === 'create'">
                    <label class="block text-xs text-gray-500 mb-2">权限分配</label>
                    <div v-if="allPermissions.length" class="max-h-60 overflow-y-auto space-y-1 border border-gray-100 rounded-lg p-3">
                        <div
                            v-for="p in allPermissions" :key="p.code"
                            class="flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors"
                            :class="roleEditForm.permissions.includes(p.code) ? 'bg-blue-50' : 'hover:bg-gray-50'"
                            @click="togglePermission(p.code)"
                        >
                            <div>
                                <div class="text-sm text-gray-700">{{ p.display_name }}</div>
                                <div class="text-xs text-gray-400">{{ p.code }} · {{ p.source }}</div>
                            </div>
                            <VortCheckbox :checked="roleEditForm.permissions.includes(p.code)" />
                        </div>
                    </div>
                    <div v-else class="text-gray-400 text-sm py-2">暂无可分配的权限</div>
                </div>
                <div v-else class="text-xs text-gray-400">
                    <Shield :size="14" class="inline mr-1" />
                    内置角色的权限不可修改
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
    </div>
</template>

import { ref, computed, watch } from "vue";
import type { Ref } from "vue";
import {
    getMembers, getRoles, getPermissions, createRole, updateRole, deleteRole,
    assignMemberRole, removeMemberRole,
} from "@/api";
import { message, dialog } from "@/components/vort";
import type { MemberItem, MemberDetail, RoleItem, PermissionItem, PermGroup } from "../types";

export interface UseContactRolesOptions {
    loadMembers: () => Promise<void>;
    openMemberDrawer: (id: string) => Promise<void>;
    currentMember: Ref<MemberDetail | null>;
}

export function useContactRoles(options: UseContactRolesOptions) {
    const roles = ref<RoleItem[]>([]);
    const loadingRoles = ref(false);
    const selectedRoleIndex = ref(0);
    const selectedRole = computed(() => roles.value[selectedRoleIndex.value] || null);
    const roleMembers = ref<MemberItem[]>([]);
    const loadingRoleMembers = ref(false);

    const allPermissions = ref<PermissionItem[]>([]);

    // ---- Permission grouping constants ----

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

    // ---- Inline permission editing ----

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

    function ensureEditingPerms() {
        if (editingPerms.value === null && selectedRole.value) {
            editingPerms.value = selectedRole.value.permissions.map(p => p.code);
        }
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

    // ---- Role edit dialog ----

    const roleEditDialogOpen = ref(false);
    const roleEditMode = ref<"create" | "edit">("create");
    const roleEditForm = ref({ name: "", display_name: "", permissions: [] as string[] });
    const roleEditId = ref<number | null>(null);
    const roleEditIsBuiltin = ref(false);
    const savingRole = ref(false);

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

    // ---- Role edit dialog permission helpers ----

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

    // ---- Load roles & permissions ----

    async function loadRoles() {
        loadingRoles.value = true;
        try {
            const res: any = await getRoles();
            roles.value = res?.roles || [];
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

    async function loadRoleMembers(roleName?: string) {
        if (!roleName) return;
        loadingRoleMembers.value = true;
        try {
            const res: any = await getMembers({ role: roleName, size: 999 });
            roleMembers.value = res?.members || [];
        } catch { roleMembers.value = []; }
        finally { loadingRoleMembers.value = false; }
    }

    // ---- Assign / remove role for a member ----

    async function handleAssignRole(memberId: string, roleName: string) {
        try {
            const res: any = await assignMemberRole(memberId, roleName);
            if (res?.success) {
                message.success("角色已分配");
                await options.loadMembers();
                if (options.currentMember.value?.id === memberId) {
                    await options.openMemberDrawer(memberId);
                }
            } else { message.error("分配失败"); }
        } catch { message.error("分配失败"); }
    }

    async function handleRemoveRole(memberId: string, roleName: string) {
        try {
            const res: any = await removeMemberRole(memberId, roleName);
            if (res?.success) {
                message.success("角色已移除");
                await options.loadMembers();
                if (options.currentMember.value?.id === memberId) {
                    await options.openMemberDrawer(memberId);
                }
            } else { message.error("移除失败"); }
        } catch { message.error("移除失败"); }
    }

    return {
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
    };
}

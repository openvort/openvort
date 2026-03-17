import { ref, computed } from "vue";
import type { Ref } from "vue";
import {
    getMembers, getDepartmentTree, createDepartment,
    updateDepartment, deleteDepartment, addDepartmentMember,
    removeDepartmentMember,
} from "@/api";
import { message, dialog } from "@/components/vort";
import type { DeptNode } from "@/components/vort-biz/dept-tree";
import type { MemberItem, MemberDetail } from "../types";

export interface UseContactDepartmentsOptions {
    selectedDeptId: Ref<number | null>;
    loadMembers: () => Promise<void>;
    membersPage: Ref<number>;
    openMemberDrawer: (id: string) => Promise<void>;
    currentMember: Ref<MemberDetail | null>;
}

export function useContactDepartments(options: UseContactDepartmentsOptions) {
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
        return options.selectedDeptId.value ? find(deptTree.value, options.selectedDeptId.value) : null;
    });

    const totalMemberCount = computed(() => {
        function sum(nodes: DeptNode[]): number {
            return nodes.reduce((acc, n) => acc + n.member_count + sum(n.children), 0);
        }
        return sum(deptTree.value);
    });

    const deptBreadcrumb = computed(() => {
        if (!options.selectedDeptId.value) return [];
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
        find(deptTree.value, options.selectedDeptId.value);
        return path;
    });

    // ---- Dept dialog ----

    const deptDialogOpen = ref(false);
    const deptDialogMode = ref<"create" | "edit">("create");
    const deptDialogParentId = ref<number | null>(null);
    const deptDialogForm = ref({ name: "" });
    const deptDialogEditId = ref<number | null>(null);
    const savingDept = ref(false);

    // ---- Add member to dept dialog ----

    const addMemberDialogOpen = ref(false);
    const addMemberSearch = ref("");
    const addMemberResults = ref<MemberItem[]>([]);
    const addMemberLoading = ref(false);

    // ---- Drawer dept dialog (add dept to member from drawer) ----

    const drawerDeptDialogOpen = ref(false);

    // ---- Load dept tree ----

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
        options.selectedDeptId.value = deptId;
        options.membersPage.value = 1;
        options.loadMembers();
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
                    if (options.selectedDeptId.value === deptId) {
                        options.selectedDeptId.value = null;
                    }
                    await Promise.all([loadDeptTree(), options.loadMembers()]);
                } else {
                    message.error("删除失败");
                    throw new Error("删除失败");
                }
            },
        });
    }

    // ---- Add/remove member from dept (dept context) ----

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
        if (!options.selectedDeptId.value) return;
        try {
            const res: any = await addDepartmentMember(options.selectedDeptId.value, memberId);
            if (res?.success) {
                message.success("已添加");
                await Promise.all([options.loadMembers(), loadDeptTree()]);
            } else { message.error("添加失败（可能已在该部门）"); }
        } catch { message.error("添加失败"); }
    }

    async function handleRemoveMemberFromDept(memberId: string) {
        if (!options.selectedDeptId.value) return;
        try {
            const res: any = await removeDepartmentMember(options.selectedDeptId.value, memberId);
            if (res?.success) {
                message.success("已从部门移除");
                await Promise.all([options.loadMembers(), loadDeptTree()]);
            } else { message.error("移除失败"); }
        } catch { message.error("移除失败"); }
    }

    // ---- Add/remove dept from member (drawer context) ----

    async function handleAddDeptToMember(deptId: number) {
        if (!options.currentMember.value) return;
        try {
            const res: any = await addDepartmentMember(deptId, options.currentMember.value.id);
            if (res?.success) {
                message.success("已添加到部门");
                await Promise.all([options.openMemberDrawer(options.currentMember.value.id), options.loadMembers()]);
            } else { message.error("添加失败（可能已在该部门）"); }
        } catch { message.error("添加失败"); }
    }

    async function handleRemoveDeptFromMember(deptId: number) {
        if (!options.currentMember.value) return;
        try {
            const res: any = await removeDepartmentMember(deptId, options.currentMember.value.id);
            if (res?.success) {
                message.success("已从部门移除");
                await Promise.all([options.openMemberDrawer(options.currentMember.value.id), options.loadMembers()]);
            } else { message.error("移除失败"); }
        } catch { message.error("移除失败"); }
    }

    return {
        deptTree, expandedDeptIds, selectedDept, totalMemberCount, deptBreadcrumb,
        loadingDepts,
        deptDialogOpen, deptDialogMode, deptDialogForm, savingDept,
        addMemberDialogOpen, addMemberSearch, addMemberResults, addMemberLoading,
        drawerDeptDialogOpen,
        loadDeptTree, handleSelectDept, handleToggleDeptExpand,
        openCreateDeptDialog, openEditDeptDialog, handleSaveDept, handleDeleteDept,
        handleSearchAddMember, handleAddMemberToDept, handleRemoveMemberFromDept,
        handleAddDeptToMember, handleRemoveDeptFromMember,
    };
}

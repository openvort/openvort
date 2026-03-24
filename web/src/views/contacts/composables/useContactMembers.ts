import { ref, computed } from "vue";
import type { Ref } from "vue";
import {
    getMembers, getMember, createMember, updateMember, resetMemberPassword,
    toggleMemberAccount, deleteMember,
    syncContacts, getSuggestions, acceptSuggestion, rejectSuggestion,
    dedupContacts, getChannels,
} from "@/api";
import { message, dialog } from "@/components/vort";
import type { MemberItem, MemberDetail, Suggestion, ChannelItem } from "../types";

export interface UseContactMembersOptions {
    selectedDeptId: Ref<number | null>;
    refreshDeptTree: () => Promise<void>;
}

export function useContactMembers(options: UseContactMembersOptions) {
    const members = ref<MemberItem[]>([]);
    const membersTotal = ref(0);
    const membersPage = ref(1);
    const membersSize = ref(50);
    const searchText = ref("");
    const filterRole = ref("");
    const loadingMembers = ref(false);
    const loadingSync = ref(false);
    const loadingDedup = ref(false);

    const channels = ref<ChannelItem[]>([]);

    const suggestions = ref<Suggestion[]>([]);
    const showSuggestions = ref(false);

    const drawerOpen = ref(false);
    const drawerLoading = ref(false);
    const currentMember = ref<MemberDetail | null>(null);
    const editForm = ref({ name: "", email: "", phone: "", position: "" });
    const savingEdit = ref(false);

    const createMemberDialogOpen = ref(false);
    const createMemberForm = ref({
        name: "", email: "", phone: "", position: "", is_account: false,
    });
    const savingCreateMember = ref(false);
    const wizardOpen = ref(false);

    const roleDialogOpen = ref(false);
    const roleDialogMember = ref<MemberItem | null>(null);
    const roleDialogLoading = ref(false);

    const selectedIds = ref<string[]>([]);

    const rowSelection = computed(() => ({
        selectedRowKeys: selectedIds.value,
        onChange: (keys: (string | number)[]) => {
            selectedIds.value = keys as string[];
        },
    }));

    // ---- Member list ----

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
            if (options.selectedDeptId.value !== null) {
                params.department_id = options.selectedDeptId.value;
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
            await Promise.all([loadMembers(), loadSuggestions(), options.refreshDeptTree()]);
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

    // ---- Suggestions ----

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

    // ---- Member drawer ----

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

    const generatedPassword = ref<{ visible: boolean; memberName: string; password: string }>({
        visible: false, memberName: "", password: "",
    });

    function showGeneratedPassword(memberName: string, password: string) {
        generatedPassword.value = { visible: true, memberName, password };
    }

    function closeGeneratedPassword() {
        generatedPassword.value = { visible: false, memberName: "", password: "" };
    }

    async function handleToggleAccount(member: MemberItem) {
        try {
            const res: any = await toggleMemberAccount(member.id);
            if (res?.success) {
                if (res.is_account && res.initial_password) {
                    showGeneratedPassword(member.name, res.initial_password);
                } else {
                    message.success(res.is_account ? "已启用登录" : "已禁用登录");
                }
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
                if (res.new_password) {
                    const name = currentMember.value?.name || memberId;
                    showGeneratedPassword(name, res.new_password);
                } else {
                    message.success("密码已重置");
                }
                if (currentMember.value?.id === memberId) {
                    await openMemberDrawer(memberId);
                }
            } else { message.error("重置失败"); }
        } catch { message.error("重置失败"); }
    }

    // ---- Create member ----

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
                if (res.initial_password) {
                    showGeneratedPassword(createMemberForm.value.name, res.initial_password);
                } else {
                    message.success("成员已创建");
                }
                createMemberDialogOpen.value = false;
                await Promise.all([loadMembers(), options.refreshDeptTree()]);
            } else {
                message.error(res?.error || "创建失败");
            }
        } catch { message.error("创建失败"); }
        finally { savingCreateMember.value = false; }
    }

    // ---- Delete member ----

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

    // ---- Role dialog (single member) ----

    function openRoleDialog(member: MemberItem) {
        roleDialogMember.value = member;
        roleDialogOpen.value = true;
    }

    return {
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
    };
}

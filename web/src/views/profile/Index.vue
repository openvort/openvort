<script setup lang="ts">
import { ref, reactive, onMounted, computed } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useUserStore } from "@/stores";
import {
    getProfile, uploadAvatar, updateProfile, changePassword,
    getNotificationPrefs, updateNotificationPrefs, getEnabledChannels,
    getGitTokens, saveGitToken, deleteGitToken,
    getMemberSkills, createPersonalSkill, updatePersonalSkill, deletePersonalSkill,
    getPublicSkills, subscribeMemberSkill, unsubscribeMemberSkill, generateMemberBioPrompt,
    getPluginPersonalSettings, getPluginPersonalSetting, savePluginPersonalSetting, deletePluginPersonalSetting,
    getAccessTokens, createAccessToken, revokeAccessToken,
} from "@/api";
import { message, dialog } from "@openvort/vort-ui";
import { z } from "zod";
import { Shield, Bell, User, GitBranch, Sparkles, Plus, Trash2, Globe, Bot, Puzzle, Key, Copy, Check } from "lucide-vue-next";
import AvatarCropper from "vue-avatar-cropper";
import "cropperjs/dist/cropper.min.css";

const userStore = useUserStore();
const route = useRoute();
const activeMenu = ref((route.query.tab as string) || "basic");
const loading = ref(false);

const profile = ref({
    member_id: "",
    name: "",
    email: "",
    phone: "",
    avatar_url: "",
    bio: "",
    roles: [] as string[],
    position: "",
    department: "",
    platform_accounts: {} as Record<string, string>
});

// 基本设置表单
const basicForm = ref({
    name: "",
    email: "",
    phone: "",
    position: "",
    department: "",
    bio: ""
});
const savingBasic = ref(false);

// 安全设置 — 修改密码
const passwordDialogOpen = ref(false);
const passwordFormRef = ref();
const passwordForm = ref({ old_password: "", new_password: "", confirm_password: "" });
const savingPassword = ref(false);
const passwordRules = z.object({
    old_password: z.string().min(1, "请输入原密码"),
    new_password: z.string().min(6, "新密码长度不能少于 6 位"),
    confirm_password: z.string().min(1, "请再次输入新密码"),
}).refine((data) => data.new_password === data.confirm_password, {
    message: "两次输入的密码不一致",
    path: ["confirm_password"],
});

// Page notification prefs (sound + desktop)
const pageSoundEnabled = ref(true);
const pageDesktopEnabled = ref(false);

function loadPageNotifyPrefs() {
    try {
        const raw = localStorage.getItem("notification-prefs");
        if (raw) {
            const p = JSON.parse(raw);
            pageSoundEnabled.value = p.sound_enabled !== false;
            pageDesktopEnabled.value = p.desktop_enabled === true;
        }
    } catch { /* silent */ }
}

function savePageNotifyPrefs() {
    localStorage.setItem("notification-prefs", JSON.stringify({
        sound_enabled: pageSoundEnabled.value,
        desktop_enabled: pageDesktopEnabled.value,
    }));
}

async function handleDesktopToggle(val: boolean) {
    if (val && typeof Notification !== "undefined" && Notification.permission !== "granted") {
        const result = await Notification.requestPermission();
        if (result !== "granted") {
            message.warning("桌面通知权限被拒绝，请在浏览器设置中允许");
            return;
        }
    }
    pageDesktopEnabled.value = val;
    savePageNotifyPrefs();
}

// IM notification prefs
const imDelaySeconds = ref(60);
const dndStart = ref("22:00");
const dndEnd = ref("08:00");

async function handleSaveImPrefs() {
    try {
        const currentPrefs: any = await getNotificationPrefs();
        const merged = {
            ...(currentPrefs || {}),
            im_notify_delay_seconds: imDelaySeconds.value,
            dnd_start: dndStart.value,
            dnd_end: dndEnd.value,
        };
        await updateNotificationPrefs(merged);
        message.success("IM 通知设置已保存");
    } catch {
        message.error("保存失败");
    }
}

// 通知设置
const notifyLoading = ref(false);
const savingNotify = ref(false);
const channels = ref<{ name: string; display_name: string; enabled: boolean }[]>([]);
// 通知类型定义
const notifyTypes = [
    { key: "system", title: "系统消息", desc: "系统公告、版本更新等通知" },
    { key: "task", title: "任务提醒", desc: "任务状态变更、到期提醒" },
    { key: "team", title: "团队动态", desc: "团队成员变更、协作通知" },
    { key: "vortflow", title: "VortFlow 通知", desc: "工作项创建、状态变更、任务分配等" },
];

// 通知偏好: { system: { web: true, wecom: false }, task: { web: true }, ... }
const notifyPrefs = ref<Record<string, Record<string, boolean>>>({});

// 平台名称映射
const platformLabels: Record<string, string> = {
    wecom: "企业微信",
    dingtalk: "钉钉",
    feishu: "飞书",
    zentao: "禅道",
    gitee: "Gitee",
    web: "Web",
};

const menuItems = [
    { key: "basic", label: "基本设置", icon: User },
    { key: "skills", label: "我的技能", icon: Sparkles },
    { key: "security", label: "安全设置", icon: Shield },
    { key: "tokens", label: "访问令牌", icon: Key },
    { key: "git", label: "Git 配置", icon: GitBranch },
    { key: "plugins", label: "插件配置", icon: Puzzle },
    { key: "notification", label: "通知设置", icon: Bell },
];

// 脱敏显示
const maskedPhone = computed(() => {
    const p = profile.value.phone;
    if (!p) return "未绑定";
    return p.replace(/(\d{3})\d{4}(\d{4})/, "$1****$2");
});
const maskedEmail = computed(() => {
    const e = profile.value.email;
    if (!e) return "未绑定";
    const [name, domain] = e.split("@");
    if (!domain) return e;
    return name.length <= 2 ? `${name}@${domain}` : `${name.slice(0, 2)}***@${domain}`;
});

// 安全设置 — 修改手机/邮箱
const phoneDialogOpen = ref(false);
const emailDialogOpen = ref(false);
const phoneFormRef = ref();
const emailFormRef = ref();
const phoneForm = ref({ phone: "" });
const emailForm = ref({ email: "" });
const savingPhone = ref(false);
const savingEmail = ref(false);
const phoneRules = z.object({
    phone: z.string().min(1, "请输入手机号").regex(/^1\d{10}$/, "请输入正确的手机号"),
});
const emailRules = z.object({
    email: z.string().min(1, "请输入邮箱地址").email("请输入正确的邮箱格式"),
});

// 安全设置项（动态计算）
const securityItems = computed(() => [
    {
        title: "账户密码",
        desc: profile.value.member_id
            ? "定期修改密码可以提高账户安全性"
            : "未设置密码",
        action: "修改",
        actionFn: () => { passwordDialogOpen.value = true; },
    },
    {
        title: "密保手机",
        desc: profile.value.phone
            ? `已绑定：${maskedPhone.value}`
            : "未绑定手机，绑定后可用于安全验证",
        action: profile.value.phone ? "修改" : "绑定",
        actionFn: () => { phoneForm.value.phone = profile.value.phone; phoneDialogOpen.value = true; },
    },
    {
        title: "备用邮箱",
        desc: profile.value.email
            ? `已绑定：${maskedEmail.value}`
            : "未绑定邮箱，绑定后可用于找回密码",
        action: profile.value.email ? "修改" : "绑定",
        actionFn: () => { emailForm.value.email = profile.value.email; emailDialogOpen.value = true; },
    },
]);

// ---- 加载数据 ----

onMounted(async () => {
    loadPageNotifyPrefs();
    if (activeMenu.value !== "basic") {
        handleMenuClick(activeMenu.value);
    }
    loading.value = true;
    try {
        const res: any = await getProfile();
        if (res) {
            Object.assign(profile.value, res);
            userStore.setUserInfo({
                ...userStore.userInfo,
                avatar_url: res.avatar_url || "",
            });
            basicForm.value = {
                name: res.name || userStore.userInfo.name || "",
                email: res.email || userStore.userInfo.email || "",
                phone: res.phone || "",
                position: res.position || userStore.userInfo.position || "",
                department: res.department || userStore.userInfo.department || "",
                bio: res.bio || "",
            };
        }
    } catch {
        basicForm.value.name = userStore.userInfo.name;
        basicForm.value.email = userStore.userInfo.email;
        basicForm.value.position = userStore.userInfo.position;
        basicForm.value.department = userStore.userInfo.department;
    } finally {
        loading.value = false;
    }
});

// ---- 基本设置保存 ----

async function handleSaveBasic() {
    savingBasic.value = true;
    try {
        await updateProfile(basicForm.value);
        // 同步更新 store
        userStore.setUserInfo({
            ...userStore.userInfo,
            name: basicForm.value.name,
            email: basicForm.value.email,
            position: basicForm.value.position,
            department: basicForm.value.department,
        });
        profile.value.name = basicForm.value.name;
        profile.value.email = basicForm.value.email;
        profile.value.phone = basicForm.value.phone;
        message.success("保存成功");
    } catch {
        message.error("保存失败");
    } finally {
        savingBasic.value = false;
    }
}

// ---- 头像上传（带裁剪） ----

const showAvatarCropper = ref(false);
const uploadingAvatar = ref(false);

async function handleAvatarUpload(cropper: any) {
    const canvas = cropper.getCroppedCanvas({ width: 512, height: 512 });
    if (!canvas) return;
    uploadingAvatar.value = true;
    try {
        const blob: Blob = await new Promise((resolve) =>
            canvas.toBlob((b: Blob) => resolve(b), "image/png", 0.9)
        );
        const file = new File([blob], "avatar.png", { type: "image/png" });
        const res: any = await uploadAvatar(file);
        if (res?.success && res.avatar_url) {
            profile.value.avatar_url = res.avatar_url;
            userStore.setUserInfo({
                ...userStore.userInfo,
                avatar_url: res.avatar_url,
            });
            message.success("头像已更新");
        } else {
            message.error(res?.error || "上传失败");
        }
    } catch {
        message.error("上传失败");
    } finally {
        uploadingAvatar.value = false;
    }
}

// ---- 修改密码 ----

async function handleChangePassword() {
    try { await passwordFormRef.value?.validate(); } catch { return; }
    savingPassword.value = true;
    try {
        await changePassword(passwordForm.value.old_password, passwordForm.value.new_password);
        message.success("密码修改成功");
        passwordDialogOpen.value = false;
        passwordForm.value = { old_password: "", new_password: "", confirm_password: "" };
    } catch (err: any) {
        message.error(err?.response?.data?.detail || "修改失败");
    } finally {
        savingPassword.value = false;
    }
}

// ---- 修改手机 ----

async function handleSavePhone() {
    try { await phoneFormRef.value?.validate(); } catch { return; }
    savingPhone.value = true;
    try {
        await updateProfile({ phone: phoneForm.value.phone });
        profile.value.phone = phoneForm.value.phone;
        message.success("手机号已更新");
        phoneDialogOpen.value = false;
    } catch {
        message.error("保存失败");
    } finally {
        savingPhone.value = false;
    }
}

// ---- 修改邮箱 ----

async function handleSaveEmail() {
    try { await emailFormRef.value?.validate(); } catch { return; }
    savingEmail.value = true;
    try {
        await updateProfile({ email: emailForm.value.email });
        profile.value.email = emailForm.value.email;
        userStore.setUserInfo({ ...userStore.userInfo, email: emailForm.value.email });
        message.success("邮箱已更新");
        emailDialogOpen.value = false;
    } catch {
        message.error("保存失败");
    } finally {
        savingEmail.value = false;
    }
}

// ---- Git Token 管理 ----

interface GitTokenItem {
    platform: string;
    username: string;
    email: string;
    has_token: boolean;
}

const gitTokens = ref<GitTokenItem[]>([]);
const gitLoading = ref(false);
const gitDialogOpen = ref(false);
const gitFormRef = ref();
const gitForm = ref({ platform: "gitee", token: "", username: "" });
const savingGitToken = ref(false);
const gitRules = z.object({
    platform: z.string().min(1),
    token: z.string().min(1, "Token 不能为空"),
    username: z.string().optional(),
});

const gitPlatforms = [
    { value: "gitee", label: "Gitee", tokenUrl: "https://gitee.com/personal_access_tokens" },
    { value: "github", label: "GitHub", tokenUrl: "https://github.com/settings/tokens" },
    { value: "gitlab", label: "GitLab", tokenUrl: "" },
];

async function loadGitTokens() {
    gitLoading.value = true;
    try {
        const res: any = await getGitTokens();
        gitTokens.value = res?.tokens || [];
    } catch {
        gitTokens.value = [];
    } finally {
        gitLoading.value = false;
    }
}

function openGitTokenDialog(platform?: string) {
    const p = platform || "gitee";
    gitForm.value = {
        platform: p,
        token: "",
        username: gitTokens.value.find((t) => t.platform === p)?.username || "",
    };
    gitDialogOpen.value = true;
}

async function handleSaveGitToken() {
    try { await gitFormRef.value?.validate(); } catch { return; }
    savingGitToken.value = true;
    try {
        await saveGitToken(gitForm.value.platform, gitForm.value.token, gitForm.value.username);
        message.success("Git Token 已保存");
        gitDialogOpen.value = false;
        await loadGitTokens();
    } catch (err: any) {
        message.error(err?.response?.data?.detail || "保存失败");
    } finally {
        savingGitToken.value = false;
    }
}

async function handleDeleteGitToken(platform: string) {
    try {
        await deleteGitToken(platform);
        message.success("已删除");
        await loadGitTokens();
    } catch {
        message.error("删除失败");
    }
}

// ---- 通知设置 ----

async function loadNotifySettings() {
    notifyLoading.value = true;
    try {
        // 加载通道列表
        const chRes: any = await getEnabledChannels();
        if (chRes?.channels) {
            // 只保留已启用的通道 + web（web 始终存在）
            const list = chRes.channels.filter((c: any) => c.enabled);
            const hasWeb = list.some((c: any) => c.name === "web");
            if (!hasWeb) {
                list.unshift({ name: "web", display_name: "Web 站内信", enabled: true });
            }
            channels.value = list;
        } else {
            channels.value = [{ name: "web", display_name: "Web 站内信", enabled: true }];
        }

        // 加载偏好
        const res: any = await getNotificationPrefs();
        if (res?.preferences) {
            notifyPrefs.value = res.preferences;
        }

        // 确保每个类型对每个通道都有值
        for (const nt of notifyTypes) {
            if (!notifyPrefs.value[nt.key]) {
                notifyPrefs.value[nt.key] = {};
            }
            for (const ch of channels.value) {
                if (notifyPrefs.value[nt.key][ch.name] === undefined) {
                    notifyPrefs.value[nt.key][ch.name] = ch.name === "web"; // web 默认开启
                }
            }
        }
    } catch {
        channels.value = [{ name: "web", display_name: "Web 站内信", enabled: true }];
    } finally {
        notifyLoading.value = false;
    }
}

async function handleSaveNotify() {
    savingNotify.value = true;
    try {
        await updateNotificationPrefs(notifyPrefs.value);
        message.success("通知设置已保存");
    } catch {
        message.error("保存失败");
    } finally {
        savingNotify.value = false;
    }
}

// ---- 我的技能 ----

interface SkillItem { id: string; name: string; description: string; content?: string; enabled?: boolean; }

const mySkills = ref<SkillItem[]>([]);
const disabledSkillIds = ref<Set<string>>(new Set());
const publicSkillsList = ref<SkillItem[]>([]);
const skillsLoading = ref(false);
const skillsLoaded = ref(false);

const mySkillDrawerOpen = ref(false);
const mySkillMode = ref<"add" | "edit">("add");
const mySkillForm = ref({ id: "", name: "", description: "", content: "" });
const mySkillSaving = ref(false);

async function loadMySkills() {
    if (!profile.value.member_id) return;
    skillsLoading.value = true;
    try {
        const [memberRes, publicRes]: any[] = await Promise.all([
            getMemberSkills(profile.value.member_id),
            getPublicSkills(),
        ]);
        mySkills.value = memberRes?.personal || [];
        publicSkillsList.value = publicRes?.skills || [];

        const disabled = new Set<string>();
        for (const id of (memberRes?.disabled_public_skill_ids || [])) disabled.add(id);
        disabledSkillIds.value = disabled;
        skillsLoaded.value = true;
    } catch { /* ignore */ }
    finally { skillsLoading.value = false; }
}

function openMySkillAdd() {
    mySkillMode.value = "add";
    mySkillForm.value = { id: "", name: "", description: "", content: "" };
    mySkillDrawerOpen.value = true;
}

function openMySkillEdit(skill: SkillItem) {
    mySkillMode.value = "edit";
    mySkillForm.value = { id: skill.id, name: skill.name, description: skill.description, content: skill.content || "" };
    mySkillDrawerOpen.value = true;
}

async function handleSaveMySkill() {
    if (!mySkillForm.value.name.trim()) { message.error("请输入名称"); return; }
    mySkillSaving.value = true;
    try {
        if (mySkillMode.value === "add") {
            await createPersonalSkill(profile.value.member_id, {
                name: mySkillForm.value.name, description: mySkillForm.value.description, content: mySkillForm.value.content,
            });
        } else {
            await updatePersonalSkill(mySkillForm.value.id, {
                name: mySkillForm.value.name, description: mySkillForm.value.description, content: mySkillForm.value.content,
            });
        }
        message.success("保存成功");
        mySkillDrawerOpen.value = false;
        loadMySkills();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "保存失败");
    } finally { mySkillSaving.value = false; }
}

function handleDeleteMySkill(skill: SkillItem) {
    dialog.confirm({
        title: `确认删除「${skill.name}」？`,
        onOk: async () => {
            try {
                await deletePersonalSkill(skill.id);
                message.success("已删除");
                loadMySkills();
            } catch { message.error("删除失败"); }
        },
    });
}

async function toggleSubscribe(skill: SkillItem) {
    const isDisabled = disabledSkillIds.value.has(skill.id);
    try {
        if (isDisabled) {
            await subscribeMemberSkill(profile.value.member_id, skill.id);
            const next = new Set(disabledSkillIds.value);
            next.delete(skill.id);
            disabledSkillIds.value = next;
            message.success("已启用");
        } else {
            await unsubscribeMemberSkill(profile.value.member_id, skill.id);
            const next = new Set(disabledSkillIds.value);
            next.add(skill.id);
            disabledSkillIds.value = next;
            message.success("已关闭");
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "操作失败");
    }
}

// ---- 插件个人配置 ----

interface PluginPersonalItem {
    plugin_name: string;
    display_name: string;
    description: string;
    schema: { key: string; label: string; type: string; required?: boolean; secret?: boolean; placeholder?: string; description?: string; options?: { value: string; label: string }[] }[];
    has_config: boolean;
}

const pluginsList = ref<PluginPersonalItem[]>([]);
const pluginsLoading = ref(false);
const pluginsLoaded = ref(false);
const pluginDialogOpen = ref(false);
const pluginDialogPlugin = ref<PluginPersonalItem | null>(null);
const pluginForm = ref<Record<string, any>>({});
const pluginSaving = ref(false);

async function loadPluginSettings() {
    pluginsLoading.value = true;
    try {
        const res: any = await getPluginPersonalSettings();
        pluginsList.value = res?.plugins || [];
        pluginsLoaded.value = true;
    } catch { pluginsList.value = []; }
    finally { pluginsLoading.value = false; }
}

async function openPluginConfig(item: PluginPersonalItem) {
    pluginDialogPlugin.value = item;
    pluginForm.value = {};
    pluginDialogOpen.value = true;
    try {
        const res: any = await getPluginPersonalSetting(item.plugin_name);
        if (res?.config) pluginForm.value = { ...res.config };
    } catch { /* ignore */ }
}

async function handleSavePluginConfig() {
    if (!pluginDialogPlugin.value) return;
    pluginSaving.value = true;
    try {
        await savePluginPersonalSetting(pluginDialogPlugin.value.plugin_name, pluginForm.value);
        message.success("配置已保存");
        pluginDialogOpen.value = false;
        loadPluginSettings();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "保存失败");
    } finally { pluginSaving.value = false; }
}

async function handleDeletePluginConfig(pluginName: string) {
    try {
        await deletePluginPersonalSetting(pluginName);
        message.success("已清除");
        loadPluginSettings();
    } catch { message.error("操作失败"); }
}

// ---- 访问令牌 (PAT) ----

interface TokenItem {
    id: string;
    name: string;
    token_prefix: string;
    expires_at: string | null;
    last_used_at: string | null;
    created_at: string | null;
}

const tokensList = ref<TokenItem[]>([]);
const tokensLoading = ref(false);
const tokensLoaded = ref(false);
const tokenDialogOpen = ref(false);
const tokenFormRef = ref();
const tokenForm = ref({ name: "", expires_days: 0 });
const creatingToken = ref(false);
const tokenRules = z.object({
    name: z.string().min(1, "请输入令牌名称"),
    expires_days: z.number(),
});

const newTokenValue = ref("");
const newTokenDialogOpen = ref(false);
const tokenCopied = ref(false);

async function loadTokens() {
    tokensLoading.value = true;
    try {
        const res: any = await getAccessTokens();
        tokensList.value = res?.tokens || [];
        tokensLoaded.value = true;
    } catch { tokensList.value = []; }
    finally { tokensLoading.value = false; }
}

function openCreateTokenDialog() {
    tokenForm.value = { name: "", expires_days: 0 };
    tokenDialogOpen.value = true;
}

async function handleCreateToken() {
    try { await tokenFormRef.value?.validate(); } catch { return; }
    creatingToken.value = true;
    try {
        const res: any = await createAccessToken(
            tokenForm.value.name.trim(),
            tokenForm.value.expires_days > 0 ? tokenForm.value.expires_days : undefined,
        );
        tokenDialogOpen.value = false;
        newTokenValue.value = res.token;
        newTokenDialogOpen.value = true;
        tokenCopied.value = false;
        loadTokens();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "创建失败");
    } finally { creatingToken.value = false; }
}

async function copyToken() {
    const text = newTokenValue.value;
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.cssText = "position:fixed;left:-9999px;top:-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
    }
    tokenCopied.value = true;
    message.success("已复制到剪贴板");
}

function handleRevokeToken(token: TokenItem) {
    dialog.confirm({
        title: `确认撤销令牌「${token.name}」？`,
        content: "撤销后使用该令牌的所有连接将立即失效，且无法恢复。",
        onOk: async () => {
            try {
                await revokeAccessToken(token.id);
                message.success("已撤销");
                loadTokens();
            } catch { message.error("撤销失败"); }
        },
    });
}

function formatTime(iso: string | null) {
    if (!iso) return "-";
    try {
        const d = new Date(iso);
        return d.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    } catch { return iso; }
}

const router = useRouter();

async function handleAiGenerateBio() {
    try {
        const res: any = await generateMemberBioPrompt(profile.value.member_id);
        if (res?.prompt) {
            router.push({ name: "chat", query: { prompt: res.prompt } });
        }
    } catch { message.error("生成失败"); }
}

// 切换菜单
function handleMenuClick(key: string) {
    activeMenu.value = key;
    router.replace({ query: key === "basic" ? {} : { tab: key } });
    if (key === "notification" && channels.value.length === 0) {
        loadNotifySettings();
    }
    if (key === "git" && gitTokens.value.length === 0 && !gitLoading.value) {
        loadGitTokens();
    }
    if (key === "skills" && !skillsLoaded.value) {
        loadMySkills();
    }
    if (key === "plugins" && !pluginsLoaded.value) {
        loadPluginSettings();
    }
    if (key === "tokens" && !tokensLoaded.value) {
        loadTokens();
    }
}
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl">
            <div class="flex flex-col md:flex-row">
                <!-- 左侧菜单 -->
                <div class="md:w-[220px] md:border-r border-b md:border-b-0 border-gray-100 py-2 md:py-4">
                    <div class="flex md:flex-col overflow-x-auto md:overflow-visible">
                        <div
                            v-for="item in menuItems"
                            :key="item.key"
                            class="h-[40px] flex items-center gap-2 px-4 md:px-6 cursor-pointer text-sm transition-colors whitespace-nowrap flex-shrink-0"
                            :class="activeMenu === item.key ? 'text-blue-600 bg-blue-50 md:border-r-2 border-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                            @click="handleMenuClick(item.key)"
                        >
                            <component :is="item.icon" :size="15" />
                            {{ item.label }}
                        </div>
                    </div>
                </div>

                <!-- 右侧内容 -->
                <div class="flex-1 p-4 md:p-8">
                    <VortSpin :spinning="loading">
                        <!-- ========== 基本设置 ========== -->
                        <div v-if="activeMenu === 'basic'">
                            <h3 class="text-base font-medium text-gray-800 mb-6">基本设置</h3>
                            <div class="flex flex-col-reverse md:flex-row gap-6 md:gap-8">
                                <div class="flex-1 max-w-[500px]">
                                    <VortForm label-width="80px">
                                        <VortFormItem label="邮箱">
                                            <span class="text-sm text-gray-600">{{ maskedEmail }}</span>
                                            <VortButton variant="link" size="small" class="ml-2" @click="activeMenu = 'security'">{{ profile.email ? '去修改' : '去绑定' }}</VortButton>
                                        </VortFormItem>
                                        <VortFormItem label="昵称"><VortInput v-model="basicForm.name" /></VortFormItem>
                                        <VortFormItem label="个人简介"><VortTextarea v-model="basicForm.bio" :rows="3" placeholder="介绍一下自己" /></VortFormItem>
                                        <VortFormItem label="职位"><VortInput v-model="basicForm.position" /></VortFormItem>
                                        <VortFormItem label="部门">
                                            <span class="text-sm text-gray-600">{{ profile.department || '未分配' }}</span>
                                        </VortFormItem>
                                        <VortFormItem label="手机">
                                            <span class="text-sm text-gray-600">{{ maskedPhone }}</span>
                                            <VortButton variant="link" size="small" class="ml-2" @click="activeMenu = 'security'">{{ profile.phone ? '去修改' : '去绑定' }}</VortButton>
                                        </VortFormItem>

                                        <!-- 平台账号展示 -->
                                        <VortFormItem v-if="Object.keys(profile.platform_accounts).length > 0" label="关联平台">
                                            <div class="flex flex-wrap gap-2">
                                                <VortTag v-for="(uid, platform) in profile.platform_accounts" :key="platform" color="blue">
                                                    {{ platformLabels[platform] || platform }}
                                                </VortTag>
                                            </div>
                                        </VortFormItem>

                                        <VortFormItem>
                                            <VortButton variant="primary" :loading="savingBasic" @click="handleSaveBasic">更新基本信息</VortButton>
                                        </VortFormItem>
                                    </VortForm>
                                </div>
                                <div class="flex md:block items-center gap-4 md:w-[200px]">
                                    <div class="text-sm text-gray-500 mb-0 md:mb-3">头像</div>
                                    <div class="w-20 h-20 md:w-[144px] md:h-[144px] rounded-full bg-blue-100 flex items-center justify-center overflow-hidden">
                                        <img v-if="profile.avatar_url" :src="profile.avatar_url" class="w-full h-full object-cover" />
                                        <span v-else class="text-3xl md:text-5xl text-blue-600 font-medium">{{ (basicForm.name || '?')[0] }}</span>
                                    </div>
                                    <VortButton class="mt-4" :loading="uploadingAvatar" @click="showAvatarCropper = true">更换头像</VortButton>
                                    <avatar-cropper
                                        v-model="showAvatarCropper"
                                        :upload-handler="handleAvatarUpload"
                                        :cropper-options="{ aspectRatio: 1, autoCropArea: 1, viewMode: 1, movable: true, zoomable: true }"
                                        :output-options="{ width: 512, height: 512 }"
                                        output-mime="image/png"
                                        :output-quality="0.9"
                                        :labels="{ submit: '确认', cancel: '取消' }"
                                        mimes="image/png, image/jpeg, image/webp"
                                    />
                                </div>
                            </div>
                        </div>

                        <!-- ========== 我的技能 ========== -->
                        <div v-else-if="activeMenu === 'skills'">
                            <div class="flex items-center justify-between mb-6">
                                <div>
                                    <h3 class="text-base font-medium text-gray-800">我的技能</h3>
                                    <p class="text-sm text-gray-400 mt-1">管理你的专业技能，AI 代理对话时会以你的技能背景回复</p>
                                </div>
                                <div class="flex items-center gap-2">
                                    <VortButton size="small" @click="handleAiGenerateBio">
                                        <Bot :size="14" class="mr-1" /> AI 生成简介
                                    </VortButton>
                                    <VortButton variant="primary" size="small" @click="openMySkillAdd">
                                        <Plus :size="14" class="mr-1" /> 添加技能
                                    </VortButton>
                                </div>
                            </div>

                            <VortSpin :spinning="skillsLoading">
                                <!-- 个人技能 -->
                                <div class="mb-6">
                                    <h4 class="text-sm font-medium text-gray-600 mb-3">个人技能</h4>
                                    <div v-if="mySkills.length === 0" class="text-center py-6 text-gray-400 text-sm bg-gray-50 rounded-lg">
                                        还没有添加个人技能，点击右上角添加
                                    </div>
                                    <div v-else class="space-y-2">
                                        <div v-for="skill in mySkills" :key="skill.id"
                                            class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100 hover:border-purple-200 transition-colors cursor-pointer"
                                            @click="openMySkillEdit(skill)">
                                            <div class="min-w-0 flex-1">
                                                <div class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</div>
                                                <div v-if="skill.description" class="text-xs text-gray-400 truncate mt-0.5">{{ skill.description }}</div>
                                            </div>
                                            <div class="flex-shrink-0 ml-3" @click.stop>
                                                <VortPopconfirm title="确认删除？" @confirm="handleDeleteMySkill(skill)">
                                                    <a class="text-gray-400 hover:text-red-500 cursor-pointer"><Trash2 :size="14" /></a>
                                                </VortPopconfirm>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- 公共技能订阅 -->
                                <div v-if="publicSkillsList.length > 0">
                                    <h4 class="text-sm font-medium text-gray-600 mb-3">公共技能订阅</h4>
                                    <p class="text-xs text-gray-400 mb-3">默认全部启用，不需要的可以关闭</p>
                                    <div class="space-y-2">
                                        <div v-for="skill in publicSkillsList" :key="skill.id"
                                            class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100">
                                            <div class="flex items-center gap-2 min-w-0">
                                                <Globe :size="14" class="text-green-500 flex-shrink-0" />
                                                <div class="min-w-0">
                                                    <div class="text-sm text-gray-800 truncate">{{ skill.name }}</div>
                                                    <div v-if="skill.description" class="text-xs text-gray-400 truncate mt-0.5">{{ skill.description }}</div>
                                                </div>
                                            </div>
                                            <VortSwitch :checked="!disabledSkillIds.has(skill.id)" size="small" @change="toggleSubscribe(skill)" />
                                        </div>
                                    </div>
                                </div>
                            </VortSpin>
                        </div>

                        <!-- ========== 安全设置 ========== -->
                        <div v-else-if="activeMenu === 'security'">
                            <h3 class="text-base font-medium text-gray-800 mb-6">安全设置</h3>
                            <div class="divide-y divide-gray-100">
                                <div v-for="item in securityItems" :key="item.title" class="flex items-center justify-between py-4">
                                    <div>
                                        <div class="text-sm font-medium text-gray-700">{{ item.title }}</div>
                                        <div class="text-sm text-gray-400 mt-1">{{ item.desc }}</div>
                                    </div>
                                    <VortButton variant="link" @click="item.actionFn">{{ item.action }}</VortButton>
                                </div>
                            </div>
                        </div>

                        <!-- ========== 访问令牌 ========== -->
                        <div v-else-if="activeMenu === 'tokens'">
                            <div class="flex items-center justify-between mb-2">
                                <h3 class="text-base font-medium text-gray-800">访问令牌</h3>
                                <VortButton variant="primary" size="small" @click="openCreateTokenDialog">
                                    <Plus :size="14" class="mr-1" /> 创建令牌
                                </VortButton>
                            </div>
                            <p class="text-sm text-gray-400 mb-6">用于 MCP 客户端（Cursor / Claude Desktop 等）认证身份。令牌创建后仅显示一次，请妥善保存。</p>

                            <VortSpin :spinning="tokensLoading">
                                <div v-if="tokensList.length === 0 && tokensLoaded" class="text-center py-8 text-gray-400 text-sm">
                                    暂无访问令牌
                                </div>
                                <div v-else class="space-y-3">
                                    <div
                                        v-for="token in tokensList"
                                        :key="token.id"
                                        class="flex items-center justify-between p-4 border border-gray-100 rounded-lg"
                                    >
                                        <div class="flex items-center gap-3 min-w-0">
                                            <div class="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center flex-shrink-0">
                                                <Key :size="16" class="text-amber-500" />
                                            </div>
                                            <div class="min-w-0">
                                                <div class="text-sm font-medium text-gray-700">{{ token.name }}</div>
                                                <div class="text-xs text-gray-400 mt-0.5 flex items-center gap-3">
                                                    <span class="font-mono">{{ token.token_prefix }}...</span>
                                                    <span>创建于 {{ formatTime(token.created_at) }}</span>
                                                    <span v-if="token.last_used_at">最近使用 {{ formatTime(token.last_used_at) }}</span>
                                                    <span v-if="token.expires_at" class="text-orange-500">{{ new Date(token.expires_at) < new Date() ? '已过期' : `${formatTime(token.expires_at)} 过期` }}</span>
                                                </div>
                                            </div>
                                        </div>
                                        <VortButton
                                            variant="link"
                                            size="small"
                                            class="text-red-500 flex-shrink-0"
                                            @click="handleRevokeToken(token)"
                                        >
                                            撤销
                                        </VortButton>
                                    </div>
                                </div>

                                <!-- 使用说明 -->
                                <div class="p-4 bg-blue-50 rounded-lg mt-6">
                                    <div class="text-sm font-medium text-blue-700 mb-2">如何使用？</div>
                                    <p class="text-xs text-blue-600 mb-2">将令牌配置到项目的 <code class="bg-blue-100 px-1 rounded">.cursor/mcp.json</code> 中：</p>
                                    <pre class="text-xs text-blue-700 bg-blue-100 rounded p-3 overflow-x-auto"><code>{
  "mcpServers": {
    "openvort": {
      "url": "http://localhost:8090/mcp/",
      "headers": {
        "Authorization": "Bearer ovt_your_token_here"
      }
    }
  }
}</code></pre>
                                    <p class="text-xs text-blue-600 mt-2">配置后 MCP 即可识别你的身份，AI 客户端可以直接说「看看我的 Bug」。</p>
                                </div>
                            </VortSpin>
                        </div>

                        <!-- ========== Git 配置 ========== -->
                        <div v-else-if="activeMenu === 'git'">
                            <h3 class="text-base font-medium text-gray-800 mb-2">Git Token 配置</h3>
                            <p class="text-sm text-gray-400 mb-6">配置个人 Git 平台 Token，用于 AI 编码任务的代码提交。每位成员需使用自己的 Token，确保提交归属正确。</p>

                            <VortSpin :spinning="gitLoading">
                                <div class="space-y-3 mb-6">
                                    <div
                                        v-for="gp in gitPlatforms"
                                        :key="gp.value"
                                        class="flex items-center justify-between p-4 border border-gray-100 rounded-lg"
                                    >
                                        <div class="flex items-center gap-3">
                                            <div class="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center">
                                                <GitBranch :size="16" class="text-gray-500" />
                                            </div>
                                            <div>
                                                <div class="text-sm font-medium text-gray-700">{{ gp.label }}</div>
                                                <div v-if="gitTokens.find(t => t.platform === gp.value)?.has_token" class="text-xs text-green-500 mt-0.5">
                                                    已配置 · {{ gitTokens.find(t => t.platform === gp.value)?.username || '' }}
                                                </div>
                                                <div v-else class="text-xs text-gray-400 mt-0.5">未配置</div>
                                            </div>
                                        </div>
                                        <div class="flex items-center gap-2">
                                            <VortButton
                                                v-if="gitTokens.find(t => t.platform === gp.value)?.has_token"
                                                variant="link"
                                                size="small"
                                                class="text-red-500"
                                                @click="handleDeleteGitToken(gp.value)"
                                            >
                                                删除
                                            </VortButton>
                                            <VortButton
                                                variant="link"
                                                size="small"
                                                @click="openGitTokenDialog(gp.value)"
                                            >
                                                {{ gitTokens.find(t => t.platform === gp.value)?.has_token ? '更新' : '配置' }}
                                            </VortButton>
                                        </div>
                                    </div>
                                </div>

                                <div class="p-4 bg-blue-50 rounded-lg">
                                    <div class="text-sm font-medium text-blue-700 mb-1">如何获取 Token？</div>
                                    <ul class="text-xs text-blue-600 space-y-1">
                                        <li>Gitee：<a href="https://gitee.com/personal_access_tokens" target="_blank" class="underline">个人设置 → 私人令牌</a></li>
                                        <li>GitHub：<a href="https://github.com/settings/tokens" target="_blank" class="underline">Settings → Developer settings → Personal access tokens</a></li>
                                        <li>GitLab：Settings → Access Tokens</li>
                                    </ul>
                                </div>
                            </VortSpin>
                        </div>

                        <!-- ========== 插件配置 ========== -->
                        <div v-else-if="activeMenu === 'plugins'">
                            <h3 class="text-base font-medium text-gray-800 mb-2">插件个人配置</h3>
                            <p class="text-sm text-gray-400 mb-6">配置你在各插件中的个人凭证（如 API Key），每位成员独立配置</p>

                            <VortSpin :spinning="pluginsLoading">
                                <div v-if="pluginsList.length === 0 && pluginsLoaded" class="text-center py-8 text-gray-400 text-sm">
                                    暂无需要个人配置的插件
                                </div>
                                <div v-else class="space-y-3">
                                    <div
                                        v-for="item in pluginsList"
                                        :key="item.plugin_name"
                                        class="flex items-center justify-between p-4 border border-gray-100 rounded-lg"
                                    >
                                        <div class="flex items-center gap-3">
                                            <div class="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center">
                                                <Puzzle :size="16" class="text-purple-500" />
                                            </div>
                                            <div>
                                                <div class="text-sm font-medium text-gray-700">{{ item.display_name }}</div>
                                                <div v-if="item.has_config" class="text-xs text-green-500 mt-0.5">已配置</div>
                                                <div v-else class="text-xs text-gray-400 mt-0.5">未配置</div>
                                            </div>
                                        </div>
                                        <div class="flex items-center gap-2">
                                            <VortButton
                                                v-if="item.has_config"
                                                variant="link"
                                                size="small"
                                                class="text-red-500"
                                                @click="handleDeletePluginConfig(item.plugin_name)"
                                            >
                                                清除
                                            </VortButton>
                                            <VortButton
                                                variant="link"
                                                size="small"
                                                @click="openPluginConfig(item)"
                                            >
                                                {{ item.has_config ? '修改' : '配置' }}
                                            </VortButton>
                                        </div>
                                    </div>
                                </div>
                            </VortSpin>
                        </div>

                        <!-- ========== 通知设置 ========== -->
                        <div v-else-if="activeMenu === 'notification'">
                            <h3 class="text-base font-medium text-gray-800 mb-2">通知设置</h3>
                            <p class="text-sm text-gray-400 mb-6">选择每种通知类型通过哪些通道接收</p>

                            <!-- Page notification settings -->
                            <div class="mb-6 space-y-4 border-b border-gray-100 pb-6">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <div class="text-sm font-medium text-gray-700">消息提示音</div>
                                        <div class="text-xs text-gray-400 mt-0.5">收到新消息时播放提示音</div>
                                    </div>
                                    <VortSwitch :checked="pageSoundEnabled" @change="(v: boolean) => { pageSoundEnabled = v; savePageNotifyPrefs(); }" />
                                </div>
                                <div class="flex items-center justify-between">
                                    <div>
                                        <div class="text-sm font-medium text-gray-700">桌面通知</div>
                                        <div class="text-xs text-gray-400 mt-0.5">浏览器不在前台时显示系统通知</div>
                                    </div>
                                    <VortSwitch :checked="pageDesktopEnabled" @change="handleDesktopToggle" />
                                </div>
                            </div>

                            <!-- IM notification settings -->
                            <div class="mb-6 space-y-4 border-b border-gray-100 pb-6">
                                <h4 class="text-sm font-medium text-gray-600">IM 通知设置</h4>
                                <div class="flex items-center justify-between">
                                    <div>
                                        <div class="text-sm font-medium text-gray-700">IM 通知延迟</div>
                                        <div class="text-xs text-gray-400 mt-0.5">消息到达后多久未读才发送 IM 提醒</div>
                                    </div>
                                    <VortSelect v-model="imDelaySeconds" :options="[
                                        { label: '30 秒', value: 30 },
                                        { label: '1 分钟', value: 60 },
                                        { label: '5 分钟', value: 300 },
                                    ]" class="w-28" />
                                </div>
                                <div class="flex items-center justify-between">
                                    <div>
                                        <div class="text-sm font-medium text-gray-700">免打扰时段</div>
                                        <div class="text-xs text-gray-400 mt-0.5">该时段内不发送 IM 提醒</div>
                                    </div>
                                    <div class="flex items-center gap-2 text-sm">
                                        <VortInput v-model="dndStart" placeholder="22:00" class="w-20 text-center" />
                                        <span class="text-gray-400">~</span>
                                        <VortInput v-model="dndEnd" placeholder="08:00" class="w-20 text-center" />
                                    </div>
                                </div>
                                <div class="mt-3">
                                    <VortButton variant="primary" size="small" @click="handleSaveImPrefs">保存 IM 设置</VortButton>
                                </div>
                            </div>

                            <VortSpin :spinning="notifyLoading">
                                <div v-if="channels.length > 0">
                                    <!-- 表头 -->
                                    <div class="flex items-center border-b border-gray-200 pb-3 mb-1">
                                        <div class="w-[200px] text-sm font-medium text-gray-500">通知类型</div>
                                        <div v-for="ch in channels" :key="ch.name" class="flex-1 text-sm font-medium text-gray-500 text-center">
                                            {{ ch.display_name || platformLabels[ch.name] || ch.name }}
                                        </div>
                                    </div>

                                    <!-- 每行一个通知类型 -->
                                    <div v-for="nt in notifyTypes" :key="nt.key" class="flex items-center py-4 border-b border-gray-50">
                                        <div class="w-[200px]">
                                            <div class="text-sm font-medium text-gray-700">{{ nt.title }}</div>
                                            <div class="text-xs text-gray-400 mt-0.5">{{ nt.desc }}</div>
                                        </div>
                                        <div v-for="ch in channels" :key="ch.name" class="flex-1 flex justify-center">
                                            <VortSwitch
                                                :checked="notifyPrefs[nt.key]?.[ch.name] ?? false"
                                                @change="(val: boolean) => { if (!notifyPrefs[nt.key]) notifyPrefs[nt.key] = {}; notifyPrefs[nt.key][ch.name] = val; }"
                                            />
                                        </div>
                                    </div>

                                    <div class="mt-6">
                                        <VortButton variant="primary" :loading="savingNotify" @click="handleSaveNotify">保存通知设置</VortButton>
                                    </div>
                                </div>

                                <div v-else class="text-center py-8 text-gray-400 text-sm">
                                    暂无可用通道
                                </div>
                            </VortSpin>
                        </div>
                    </VortSpin>
                </div>
            </div>
        </div>
    </div>

    <!-- 修改密码弹窗 -->
    <VortDialog
        :open="passwordDialogOpen"
        title="修改密码"
        :confirm-loading="savingPassword"
        ok-text="确认修改"
        @ok="handleChangePassword"
        @update:open="passwordDialogOpen = $event"
    >
        <VortForm ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="100px" class="mt-4">
            <VortFormItem label="原密码" name="old_password" required>
                <VortInputPassword v-model="passwordForm.old_password" placeholder="请输入原密码" />
            </VortFormItem>
            <VortFormItem label="新密码" name="new_password" required>
                <VortInputPassword v-model="passwordForm.new_password" placeholder="至少 6 位" />
            </VortFormItem>
            <VortFormItem label="确认新密码" name="confirm_password" required>
                <VortInputPassword v-model="passwordForm.confirm_password" placeholder="再次输入新密码" />
            </VortFormItem>
        </VortForm>
    </VortDialog>

    <!-- 修改手机弹窗 -->
    <VortDialog
        :open="phoneDialogOpen"
        title="修改手机号"
        :confirm-loading="savingPhone"
        ok-text="确认"
        @ok="handleSavePhone"
        @update:open="phoneDialogOpen = $event"
    >
        <VortForm ref="phoneFormRef" :model="phoneForm" :rules="phoneRules" label-width="80px" class="mt-4">
            <VortFormItem label="手机号" name="phone" required>
                <VortInput v-model="phoneForm.phone" placeholder="请输入手机号" />
            </VortFormItem>
        </VortForm>
    </VortDialog>

    <!-- 修改邮箱弹窗 -->
    <VortDialog
        :open="emailDialogOpen"
        title="修改邮箱"
        :confirm-loading="savingEmail"
        ok-text="确认"
        @ok="handleSaveEmail"
        @update:open="emailDialogOpen = $event"
    >
        <VortForm ref="emailFormRef" :model="emailForm" :rules="emailRules" label-width="80px" class="mt-4">
            <VortFormItem label="邮箱" name="email" required>
                <VortInput v-model="emailForm.email" placeholder="请输入邮箱地址" />
            </VortFormItem>
        </VortForm>
    </VortDialog>

    <!-- Git Token 配置弹窗 -->
    <VortDialog
        :open="gitDialogOpen"
        title="配置 Git Token"
        :confirm-loading="savingGitToken"
        ok-text="保存"
        @ok="handleSaveGitToken"
        @update:open="gitDialogOpen = $event"
    >
        <VortForm ref="gitFormRef" :model="gitForm" :rules="gitRules" label-width="100px" class="mt-4">
            <VortFormItem label="平台" name="platform">
                <VortSelect v-model="gitForm.platform" :disabled="true">
                    <option v-for="gp in gitPlatforms" :key="gp.value" :value="gp.value">{{ gp.label }}</option>
                </VortSelect>
            </VortFormItem>
            <VortFormItem label="用户名" name="username">
                <VortInput v-model="gitForm.username" placeholder="平台用户名（用于提交归属）" />
            </VortFormItem>
            <VortFormItem label="Access Token" name="token" required>
                <VortInputPassword v-model="gitForm.token" placeholder="粘贴你的 Personal Access Token" />
            </VortFormItem>
            <div class="flex justify-end">
                <a
                    v-if="gitPlatforms.find(p => p.value === gitForm.platform)?.tokenUrl"
                    :href="gitPlatforms.find(p => p.value === gitForm.platform)?.tokenUrl"
                    target="_blank"
                    class="text-xs text-blue-500 hover:underline"
                >去生成 Token →</a>
            </div>
        </VortForm>
    </VortDialog>

    <!-- 插件个人配置弹窗 -->
    <VortDialog
        :open="pluginDialogOpen"
        :title="pluginDialogPlugin ? `配置 ${pluginDialogPlugin.display_name}` : '插件配置'"
        :confirm-loading="pluginSaving"
        ok-text="保存"
        @ok="handleSavePluginConfig"
        @update:open="pluginDialogOpen = $event"
    >
        <div v-if="pluginDialogPlugin?.description" class="text-xs text-gray-400 mb-4">{{ pluginDialogPlugin.description }}</div>
        <VortForm label-width="120px" class="mt-2">
            <VortFormItem
                v-for="field in (pluginDialogPlugin?.schema || [])"
                :key="field.key"
                :label="field.label"
                :required="field.required"
            >
                <VortInputPassword
                    v-if="field.secret"
                    v-model="pluginForm[field.key]"
                    :placeholder="field.placeholder"
                />
                <VortSelect
                    v-else-if="field.type === 'select' && field.options"
                    v-model="pluginForm[field.key]"
                    :options="field.options"
                    :placeholder="field.placeholder"
                />
                <VortSwitch v-else-if="field.type === 'boolean'" :checked="pluginForm[field.key] === true || pluginForm[field.key] === 'true'" @update:checked="pluginForm[field.key] = $event" />
                <VortInput v-else v-model="pluginForm[field.key]" :placeholder="field.placeholder" />
                <div v-if="field.description" class="text-xs text-gray-400 mt-1">{{ field.description }}</div>
            </VortFormItem>
        </VortForm>
    </VortDialog>

    <!-- 创建访问令牌弹窗 -->
    <VortDialog
        :open="tokenDialogOpen"
        title="创建访问令牌"
        :confirm-loading="creatingToken"
        ok-text="创建"
        @ok="handleCreateToken"
        @update:open="tokenDialogOpen = $event"
    >
        <VortForm ref="tokenFormRef" :model="tokenForm" :rules="tokenRules" label-width="100px" class="mt-4">
            <VortFormItem label="令牌名称" name="name" required>
                <VortInput v-model="tokenForm.name" placeholder="如：Cursor MCP、Claude Desktop" />
            </VortFormItem>
            <VortFormItem label="有效期" name="expires_days">
                <VortSelect v-model="tokenForm.expires_days" :options="[
                    { label: '永不过期', value: 0 },
                    { label: '30 天', value: 30 },
                    { label: '90 天', value: 90 },
                    { label: '365 天', value: 365 },
                ]" />
            </VortFormItem>
        </VortForm>
    </VortDialog>

    <!-- 新令牌展示弹窗 -->
    <VortDialog :open="newTokenDialogOpen" title="令牌已创建" :footer="false" :closable="false" @update:open="newTokenDialogOpen = $event">
        <div class="mt-2">
            <div class="p-3 bg-amber-50 border border-amber-200 rounded-lg mb-4">
                <p class="text-sm text-amber-800 font-medium">请立即复制并妥善保存此令牌，关闭后将无法再次查看。</p>
            </div>
            <div class="flex items-center gap-2">
                <code class="flex-1 text-sm bg-gray-100 rounded px-3 py-2 font-mono break-all select-all">{{ newTokenValue }}</code>
                <VortButton size="small" @click="copyToken">
                    <Check v-if="tokenCopied" :size="14" class="text-green-500" />
                    <Copy v-else :size="14" />
                </VortButton>
            </div>
            <div class="mt-4 flex justify-end">
                <VortButton variant="primary" @click="newTokenDialogOpen = false">我已保存，关闭</VortButton>
            </div>
        </div>
    </VortDialog>

    <!-- 个人技能编辑弹窗 -->
    <VortDialog
        :open="mySkillDrawerOpen"
        :title="mySkillMode === 'add' ? '添加技能' : '编辑技能'"
        :width="520"
        :confirm-loading="mySkillSaving"
        @ok="handleSaveMySkill"
        @update:open="mySkillDrawerOpen = $event"
    >
        <VortForm label-width="80px" class="mt-2">
            <VortFormItem label="名称" required>
                <VortInput v-model="mySkillForm.name" placeholder="如：Python 开发、项目管理" />
            </VortFormItem>
            <VortFormItem label="描述">
                <VortInput v-model="mySkillForm.description" placeholder="简短描述" />
            </VortFormItem>
            <VortFormItem label="详细内容">
                <VortTextarea v-model="mySkillForm.content"
                    placeholder="详细描述你在此技能方面的专业知识、经验和能力..." :rows="8"
                    style="font-family: monospace; font-size: 13px;" />
            </VortFormItem>
        </VortForm>
    </VortDialog>
</template>

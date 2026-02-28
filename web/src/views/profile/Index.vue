<script setup lang="ts">
import { ref, reactive, onMounted, computed } from "vue";
import { useUserStore } from "@/stores";
import { getProfile, uploadAvatar, updateProfile, changePassword, getNotificationPrefs, updateNotificationPrefs, getEnabledChannels } from "@/api";
import { message } from "@/components/vort/message";
import { Shield, Bell, User, Lock, Mail, Smartphone, KeyRound } from "lucide-vue-next";

const userStore = useUserStore();
const activeMenu = ref("basic");
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
const passwordForm = reactive({ old_password: "", new_password: "", confirm_password: "" });
const savingPassword = ref(false);

// 通知设置
const notifyLoading = ref(false);
const savingNotify = ref(false);
const channels = ref<{ name: string; display_name: string; enabled: boolean }[]>([]);
// 通知类型定义
const notifyTypes = [
    { key: "system", title: "系统消息", desc: "系统公告、版本更新等通知" },
    { key: "task", title: "任务提醒", desc: "任务状态变更、到期提醒" },
    { key: "team", title: "团队动态", desc: "团队成员变更、协作通知" },
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
    { key: "security", label: "安全设置", icon: Shield },
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
const phoneForm = reactive({ phone: "" });
const emailForm = reactive({ email: "" });
const savingPhone = ref(false);
const savingEmail = ref(false);

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
        actionFn: () => { phoneForm.phone = profile.value.phone; phoneDialogOpen.value = true; },
    },
    {
        title: "备用邮箱",
        desc: profile.value.email
            ? `已绑定：${maskedEmail.value}`
            : "未绑定邮箱，绑定后可用于找回密码",
        action: profile.value.email ? "修改" : "绑定",
        actionFn: () => { emailForm.email = profile.value.email; emailDialogOpen.value = true; },
    },
]);

// ---- 加载数据 ----

onMounted(async () => {
    loading.value = true;
    try {
        const res: any = await getProfile();
        if (res) {
            Object.assign(profile.value, res);
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

// ---- 头像上传 ----

const avatarInput = ref<HTMLInputElement | null>(null);
const uploadingAvatar = ref(false);

function triggerAvatarUpload() {
    avatarInput.value?.click();
}

async function handleAvatarChange(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    uploadingAvatar.value = true;
    try {
        const res: any = await uploadAvatar(file);
        if (res?.success && res.avatar_url) {
            profile.value.avatar_url = res.avatar_url;
            message.success("头像已更新");
        } else {
            message.error(res?.error || "上传失败");
        }
    } catch {
        message.error("上传失败");
    } finally {
        uploadingAvatar.value = false;
        if (avatarInput.value) avatarInput.value.value = "";
    }
}

// ---- 修改密码 ----

async function handleChangePassword() {
    if (!passwordForm.new_password || passwordForm.new_password.length < 6) {
        message.error("新密码长度不能少于 6 位");
        return;
    }
    if (passwordForm.new_password !== passwordForm.confirm_password) {
        message.error("两次输入的密码不一致");
        return;
    }
    savingPassword.value = true;
    try {
        await changePassword(passwordForm.old_password, passwordForm.new_password);
        message.success("密码修改成功");
        passwordDialogOpen.value = false;
        passwordForm.old_password = "";
        passwordForm.new_password = "";
        passwordForm.confirm_password = "";
    } catch (err: any) {
        message.error(err?.response?.data?.detail || "修改失败");
    } finally {
        savingPassword.value = false;
    }
}

// ---- 修改手机 ----

async function handleSavePhone() {
    savingPhone.value = true;
    try {
        await updateProfile({ phone: phoneForm.phone });
        profile.value.phone = phoneForm.phone;
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
    savingEmail.value = true;
    try {
        await updateProfile({ email: emailForm.email });
        profile.value.email = emailForm.email;
        userStore.setUserInfo({ ...userStore.userInfo, email: emailForm.email });
        message.success("邮箱已更新");
        emailDialogOpen.value = false;
    } catch {
        message.error("保存失败");
    } finally {
        savingEmail.value = false;
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

// 切换到通知 tab 时加载
function handleMenuClick(key: string) {
    activeMenu.value = key;
    if (key === "notification" && channels.value.length === 0) {
        loadNotifySettings();
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
                                    <input ref="avatarInput" type="file" accept="image/jpeg,image/png,image/gif,image/webp" class="hidden" @change="handleAvatarChange" />
                                    <VortButton class="mt-4" :loading="uploadingAvatar" @click="triggerAvatarUpload">更换头像</VortButton>
                                </div>
                            </div>
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

                        <!-- ========== 通知设置 ========== -->
                        <div v-else-if="activeMenu === 'notification'">
                            <h3 class="text-base font-medium text-gray-800 mb-2">通知设置</h3>
                            <p class="text-sm text-gray-400 mb-6">选择每种通知类型通过哪些通道接收</p>

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
    <VortDialog :open="passwordDialogOpen" title="修改密码" :footer="false" @update:open="passwordDialogOpen = $event">
        <VortForm label-width="100px" class="mt-4">
            <VortFormItem label="原密码" required>
                <VortInputPassword v-model="passwordForm.old_password" placeholder="请输入原密码" />
            </VortFormItem>
            <VortFormItem label="新密码" required>
                <VortInputPassword v-model="passwordForm.new_password" placeholder="至少 6 位" />
            </VortFormItem>
            <VortFormItem label="确认新密码" required>
                <VortInputPassword v-model="passwordForm.confirm_password" placeholder="再次输入新密码" />
            </VortFormItem>
            <VortFormItem>
                <div class="flex gap-3">
                    <VortButton variant="primary" :loading="savingPassword" @click="handleChangePassword">确认修改</VortButton>
                    <VortButton @click="passwordDialogOpen = false">取消</VortButton>
                </div>
            </VortFormItem>
        </VortForm>
    </VortDialog>

    <!-- 修改手机弹窗 -->
    <VortDialog :open="phoneDialogOpen" title="修改手机号" :footer="false" @update:open="phoneDialogOpen = $event">
        <VortForm label-width="80px" class="mt-4">
            <VortFormItem label="手机号" required>
                <VortInput v-model="phoneForm.phone" placeholder="请输入手机号" />
            </VortFormItem>
            <VortFormItem>
                <div class="flex gap-3">
                    <VortButton variant="primary" :loading="savingPhone" @click="handleSavePhone">确认</VortButton>
                    <VortButton @click="phoneDialogOpen = false">取消</VortButton>
                </div>
            </VortFormItem>
        </VortForm>
    </VortDialog>

    <!-- 修改邮箱弹窗 -->
    <VortDialog :open="emailDialogOpen" title="修改邮箱" :footer="false" @update:open="emailDialogOpen = $event">
        <VortForm label-width="80px" class="mt-4">
            <VortFormItem label="邮箱" required>
                <VortInput v-model="emailForm.email" placeholder="请输入邮箱地址" />
            </VortFormItem>
            <VortFormItem>
                <div class="flex gap-3">
                    <VortButton variant="primary" :loading="savingEmail" @click="handleSaveEmail">确认</VortButton>
                    <VortButton @click="emailDialogOpen = false">取消</VortButton>
                </div>
            </VortFormItem>
        </VortForm>
    </VortDialog>
</template>

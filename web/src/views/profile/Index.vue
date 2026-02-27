<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useUserStore } from "@/stores";
import { getProfile, uploadAvatar } from "@/api";
import { message } from "@/components/vort/message";

const userStore = useUserStore();
const activeMenu = ref("basic");
const loading = ref(false);

const profile = ref({
    member_id: "",
    name: "",
    email: "",
    phone: "",
    avatar_url: "",
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

// 安全设置
const securityItems = [
    { title: "账户密码", desc: "当前密码强度：强", action: "修改" },
    { title: "密保手机", desc: "未绑定手机", action: "绑定" },
    { title: "备用邮箱", desc: "未绑定备用邮箱", action: "绑定" },
    { title: "MFA 设备", desc: "未绑定 MFA 设备，绑定后可以进行二次确认", action: "绑定" }
];

// 通知设置
const notifySettings = ref([
    { title: "系统消息", desc: "系统消息将以站内信的形式通知", checked: true },
    { title: "任务提醒", desc: "任务状态变更将以站内信的形式通知", checked: true },
    { title: "团队动态", desc: "团队成员的动态将以站内信的形式通知", checked: false }
]);

const menuItems = [
    { key: "basic", label: "基本设置" },
    { key: "security", label: "安全设置" },
    { key: "notification", label: "通知设置" }
];

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
                bio: res.bio || ""
            };
            // 更新安全设置描述
            if (res.phone) {
                const masked = res.phone.replace(/(\d{3})\d{4}(\d{4})/, "$1****$2");
                securityItems[1].desc = `已绑定手机：${masked}`;
                securityItems[1].action = "修改";
            }
            if (res.email) {
                securityItems[2].desc = `已绑定邮箱：${res.email}`;
                securityItems[2].action = "修改";
            }
        }
    } catch {
        // 使用 store 中的数据
        basicForm.value.name = userStore.userInfo.name;
        basicForm.value.email = userStore.userInfo.email;
        basicForm.value.position = userStore.userInfo.position;
        basicForm.value.department = userStore.userInfo.department;
    } finally {
        loading.value = false;
    }
});

const handleSave = () => {
    message.success("保存成功");
};

// 头像上传
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
        // 重置 input 以便再次选择同一文件
        if (avatarInput.value) avatarInput.value.value = "";
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
                            class="h-[40px] flex items-center px-4 md:px-6 cursor-pointer text-sm transition-colors whitespace-nowrap flex-shrink-0"
                            :class="activeMenu === item.key ? 'text-blue-600 bg-blue-50 md:border-r-2 border-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                            @click="activeMenu = item.key"
                        >
                            {{ item.label }}
                        </div>
                    </div>
                </div>

                <!-- 右侧内容 -->
                <div class="flex-1 p-4 md:p-8">
                    <VortSpin :spinning="loading">
                        <!-- 基本设置 -->
                        <div v-if="activeMenu === 'basic'">
                            <h3 class="text-base font-medium text-gray-800 mb-6">基本设置</h3>
                            <div class="flex flex-col-reverse md:flex-row gap-6 md:gap-8">
                                <div class="flex-1 max-w-[500px]">
                                    <VortForm label-width="80px">
                                        <VortFormItem label="邮箱"><VortInput v-model="basicForm.email" /></VortFormItem>
                                        <VortFormItem label="昵称"><VortInput v-model="basicForm.name" /></VortFormItem>
                                        <VortFormItem label="个人简介"><VortTextarea v-model="basicForm.bio" :rows="3" /></VortFormItem>
                                        <VortFormItem label="职位"><VortInput v-model="basicForm.position" /></VortFormItem>
                                        <VortFormItem label="部门"><VortInput v-model="basicForm.department" /></VortFormItem>
                                        <VortFormItem label="手机"><VortInput v-model="basicForm.phone" /></VortFormItem>
                                        <VortFormItem>
                                            <VortButton variant="primary" @click="handleSave">更新基本信息</VortButton>
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

                        <!-- 安全设置 -->
                        <div v-else-if="activeMenu === 'security'">
                            <h3 class="text-base font-medium text-gray-800 mb-6">安全设置</h3>
                            <div class="divide-y divide-gray-100">
                                <div v-for="item in securityItems" :key="item.title" class="flex items-center justify-between py-4">
                                    <div>
                                        <div class="text-sm font-medium text-gray-700">{{ item.title }}</div>
                                        <div class="text-sm text-gray-400 mt-1">{{ item.desc }}</div>
                                    </div>
                                    <a class="text-sm text-blue-600 cursor-pointer hover:text-blue-500">{{ item.action }}</a>
                                </div>
                            </div>
                        </div>

                        <!-- 通知设置 -->
                        <div v-else-if="activeMenu === 'notification'">
                            <h3 class="text-base font-medium text-gray-800 mb-6">通知设置</h3>
                            <div class="divide-y divide-gray-100">
                                <div v-for="item in notifySettings" :key="item.title" class="flex items-center justify-between py-4">
                                    <div>
                                        <div class="text-sm font-medium text-gray-700">{{ item.title }}</div>
                                        <div class="text-sm text-gray-400 mt-1">{{ item.desc }}</div>
                                    </div>
                                    <VortSwitch v-model:checked="item.checked" />
                                </div>
                            </div>
                        </div>
                    </VortSpin>
                </div>
            </div>
        </div>
    </div>
</template>

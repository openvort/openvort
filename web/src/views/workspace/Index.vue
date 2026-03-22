<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useUserStore } from "@/stores";
import { useRouter } from "vue-router";
import { getWorkspace } from "@/api";
import { MessageSquare, Bot, Settings, Users } from "lucide-vue-next";

const userStore = useUserStore();
const router = useRouter();

const workspace = ref({
    chat_count: 0,
    recent_chats: [] as any[]
});

const greeting = ref("");

onMounted(async () => {
    // 问候语
    const hour = new Date().getHours();
    if (hour < 9) greeting.value = "早上好";
    else if (hour < 12) greeting.value = "上午好";
    else if (hour < 14) greeting.value = "中午好";
    else if (hour < 18) greeting.value = "下午好";
    else greeting.value = "晚上好";

    try {
        const res: any = await getWorkspace();
        if (res) Object.assign(workspace.value, res);
    } catch { /* ignore */ }
});

const shortcuts = [
    { title: "AI 助手", icon: MessageSquare, desc: "和 AI 对话，管理任务", path: "/chat", color: "blue" },
    { title: "个人设置", icon: Settings, desc: "修改个人信息", path: "/profile", color: "gray" },
];

const adminShortcuts = [
    { title: "联系人", icon: Users, desc: "管理团队成员", path: "/contacts", color: "purple" },
    { title: "插件管理", icon: Bot, desc: "查看已加载插件", path: "/plugins", color: "orange" },
];
</script>

<template>
    <div class="space-y-6">
        <!-- 欢迎横幅 -->
        <div class="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg p-6 text-white">
            <h2 class="text-xl font-medium">{{ greeting }}，{{ userStore.userInfo.name || '用户' }}</h2>
            <p class="text-blue-100 text-sm mt-1">
                {{ userStore.userInfo.position || '' }}
                {{ userStore.userInfo.department ? `· ${userStore.userInfo.department}` : '' }}
            </p>
            <div class="flex items-center gap-6 mt-4 text-sm">
                <div>
                    <span class="text-blue-200">对话次数</span>
                    <span class="ml-2 text-lg font-semibold">{{ workspace.chat_count }}</span>
                </div>
                <div>
                    <span class="text-blue-200">角色</span>
                    <span class="ml-2">{{ userStore.userInfo.roles.join(', ') || '成员' }}</span>
                </div>
            </div>
        </div>

        <!-- 快捷入口 -->
        <div>
            <h3 class="text-sm font-medium text-gray-700 mb-3">快捷入口</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <vort-card
                    v-for="item in shortcuts"
                    :key="item.title"
                    :shadow="false"
                    padding="small"
                    class="cursor-pointer hover:bg-gray-50 transition-colors"
                    @click="router.push(item.path)"
                >
                    <div class="w-10 h-10 rounded-lg flex items-center justify-center mb-3"
                        :class="`bg-${item.color}-50`">
                        <component :is="item.icon" :size="20" :class="`text-${item.color}-600`" />
                    </div>
                    <h4 class="text-sm font-medium text-gray-800">{{ item.title }}</h4>
                    <p class="text-xs text-gray-400 mt-0.5">{{ item.desc }}</p>
                </vort-card>
                <template v-if="userStore.isAdmin">
                    <vort-card
                        v-for="item in adminShortcuts"
                        :key="item.title"
                        :shadow="false"
                        padding="small"
                        class="cursor-pointer hover:bg-gray-50 transition-colors"
                        @click="router.push(item.path)"
                    >
                        <div class="w-10 h-10 rounded-lg flex items-center justify-center mb-3"
                            :class="`bg-${item.color}-50`">
                            <component :is="item.icon" :size="20" :class="`text-${item.color}-600`" />
                        </div>
                        <h4 class="text-sm font-medium text-gray-800">{{ item.title }}</h4>
                        <p class="text-xs text-gray-400 mt-0.5">{{ item.desc }}</p>
                    </vort-card>
                </template>
            </div>
        </div>
    </div>
</template>

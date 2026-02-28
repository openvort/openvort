<script setup lang="ts">
import { useRouter } from "vue-router";
import { useUserStore } from "@/stores";
import { MessageSquare, Settings, Users, Bot } from "lucide-vue-next";

const router = useRouter();
const userStore = useUserStore();

const shortcuts = [
    { title: "AI 助手", icon: MessageSquare, desc: "和 AI 对话", path: "/chat", color: "blue" },
    { title: "个人设置", icon: Settings, desc: "修改个人信息", path: "/profile", color: "gray" },
];

const adminShortcuts = [
    { title: "成员管理", icon: Users, desc: "管理团队成员", path: "/contacts", color: "purple" },
    { title: "插件管理", icon: Bot, desc: "查看已加载插件", path: "/plugins", color: "orange" },
];

const colorMap: Record<string, { bg: string; text: string }> = {
    blue: { bg: "bg-blue-50", text: "text-blue-600" },
    gray: { bg: "bg-gray-100", text: "text-gray-600" },
    purple: { bg: "bg-purple-50", text: "text-purple-600" },
    orange: { bg: "bg-orange-50", text: "text-orange-600" },
};
</script>

<template>
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
                    :class="colorMap[item.color]?.bg">
                    <component :is="item.icon" :size="20" :class="colorMap[item.color]?.text" />
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
                        :class="colorMap[item.color]?.bg">
                        <component :is="item.icon" :size="20" :class="colorMap[item.color]?.text" />
                    </div>
                    <h4 class="text-sm font-medium text-gray-800">{{ item.title }}</h4>
                    <p class="text-xs text-gray-400 mt-0.5">{{ item.desc }}</p>
                </vort-card>
            </template>
        </div>
    </div>
</template>

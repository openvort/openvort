<script setup lang="ts">
import { useRouter } from "vue-router";
import { useUserStore } from "@/stores";
import {
    MessageSquare, Settings, Users, Puzzle, LayoutDashboard,
    FileText, Clock, GitBranch,
} from "lucide-vue-next";

const router = useRouter();
const userStore = useUserStore();

const shortcuts = [
    { title: "AI 助手", icon: MessageSquare, desc: "和 AI 对话", path: "/chat", gradient: "from-blue-500 to-blue-600" },
    { title: "项目看板", icon: LayoutDashboard, desc: "项目管理", path: "/vortflow/board", gradient: "from-indigo-500 to-indigo-600" },
    { title: "汇报中心", icon: FileText, desc: "日报/周报/月报", path: "/reports", gradient: "from-emerald-500 to-emerald-600" },
    { title: "计划任务", icon: Clock, desc: "自动化任务", path: "/schedules", gradient: "from-amber-500 to-amber-600" },
];

const adminShortcuts = [
    { title: "成员管理", icon: Users, desc: "管理团队成员", path: "/contacts", gradient: "from-purple-500 to-purple-600" },
    { title: "插件管理", icon: Puzzle, desc: "查看已加载插件", path: "/plugins", gradient: "from-rose-500 to-rose-600" },
    { title: "代码仓库", icon: GitBranch, desc: "Git 仓库管理", path: "/vortgit/repos", gradient: "from-cyan-500 to-cyan-600" },
    { title: "个人设置", icon: Settings, desc: "修改个人信息", path: "/profile", gradient: "from-slate-500 to-slate-600" },
];
</script>

<template>
    <div>
        <h3 class="text-sm font-medium text-gray-700 mb-3">快捷入口</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div
                v-for="item in shortcuts"
                :key="item.title"
                class="group relative bg-white rounded-xl border border-gray-100 p-4 cursor-pointer hover:shadow-md hover:border-transparent transition-all duration-200"
                @click="router.push(item.path)"
            >
                <div
                    class="w-10 h-10 rounded-xl flex items-center justify-center mb-3 bg-gradient-to-br shadow-sm"
                    :class="item.gradient"
                >
                    <component :is="item.icon" :size="20" class="text-white" />
                </div>
                <h4 class="text-sm font-medium text-gray-800 group-hover:text-blue-600 transition-colors">{{ item.title }}</h4>
                <p class="text-xs text-gray-400 mt-0.5">{{ item.desc }}</p>
            </div>
            <template v-if="userStore.isAdmin">
                <div
                    v-for="item in adminShortcuts"
                    :key="item.title"
                    class="group relative bg-white rounded-xl border border-gray-100 p-4 cursor-pointer hover:shadow-md hover:border-transparent transition-all duration-200"
                    @click="router.push(item.path)"
                >
                    <div
                        class="w-10 h-10 rounded-xl flex items-center justify-center mb-3 bg-gradient-to-br shadow-sm"
                        :class="item.gradient"
                    >
                        <component :is="item.icon" :size="20" class="text-white" />
                    </div>
                    <h4 class="text-sm font-medium text-gray-800 group-hover:text-blue-600 transition-colors">{{ item.title }}</h4>
                    <p class="text-xs text-gray-400 mt-0.5">{{ item.desc }}</p>
                </div>
            </template>
        </div>
    </div>
</template>

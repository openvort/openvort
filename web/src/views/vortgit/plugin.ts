import type { PluginFrontendConfig } from "@/types/plugin";

export default {
    id: "vortgit",

    routes: [
        { path: "vortgit/repos", name: "vortgit-repos", component: () => import("./Repos.vue"), meta: { title: "代码仓库" } },
        { path: "vortgit/code-tasks", name: "vortgit-code-tasks", component: () => import("./CodeTasks.vue"), meta: { title: "编码任务" } },
        { path: "vortgit/providers", name: "vortgit-providers", component: () => import("./Providers.vue"), meta: { title: "平台管理" } },
    ],

    menus: [
        {
            title: "VortGit", icon: "git-branch",
            children: [
                { title: "代码仓库", icon: "folder-git-2", path: "/vortgit/repos" },
                { title: "编码任务", icon: "terminal-square", path: "/vortgit/code-tasks" },
            ],
        },
    ],
} satisfies PluginFrontendConfig;

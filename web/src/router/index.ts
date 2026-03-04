import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";
import { useUserStore, usePluginStore } from "@/stores";
import { registerPluginRoutes } from "@/router/pluginRoutes";

const BasicLayout = () => import("@/layouts/BasicLayout.vue");
const BlankLayout = () => import("@/layouts/BlankLayout.vue");

const routes: RouteRecordRaw[] = [
    {
        path: "/login",
        component: BlankLayout,
        children: [{ path: "", name: "login", component: () => import("@/views/login/Index.vue"), meta: { title: "登录" } }]
    },
    {
        path: "/",
        name: "root",
        component: BasicLayout,
        redirect: "/overview",
        children: [
            // 所有角色可访问
            { path: "chat", name: "chat", component: () => import("@/views/chat/Index.vue"), meta: { title: "AI 助手", fullscreen: true } },
            { path: "overview", name: "overview", component: () => import("@/views/overview/Index.vue"), meta: { title: "概览" } },
            { path: "schedules", name: "schedules", component: () => import("@/views/schedules/Index.vue"), meta: { title: "定时任务" } },
            { path: "reports", name: "reports", component: () => import("@/views/reports/Index.vue"), meta: { title: "汇报中心" } },
            { path: "profile", name: "profile", component: () => import("@/views/profile/Index.vue"), meta: { title: "个人设置" } },
            // VortFlow
            { path: "vortflow/board", name: "vortflow-board", component: () => import("@/views/vortflow/Board.vue"), meta: { title: "项目看板" } },
            { path: "vortflow/stories", name: "vortflow-stories", component: () => import("@/views/vortflow/Stories.vue"), meta: { title: "需求列表" } },
            { path: "vortflow/tasks", name: "vortflow-tasks", component: () => import("@/views/vortflow/Tasks.vue"), meta: { title: "任务管理" } },
            { path: "vortflow/bugs", name: "vortflow-bugs", component: () => import("@/views/vortflow/Bugs.vue"), meta: { title: "缺陷跟踪" } },
            { path: "vortflow/milestones", name: "vortflow-milestones", component: () => import("@/views/vortflow/Milestones.vue"), meta: { title: "里程碑" } },
            { path: "vortflow/projects/:id", name: "vortflow-project-detail", component: () => import("@/views/vortflow/ProjectDetail.vue"), meta: { title: "项目详情" } },
            // VortGit
            { path: "vortgit/repos", name: "vortgit-repos", component: () => import("@/views/vortgit/Repos.vue"), meta: { title: "代码仓库" } },
            { path: "vortgit/code-tasks", name: "vortgit-code-tasks", component: () => import("@/views/vortgit/CodeTasks.vue"), meta: { title: "编码任务" } },
            { path: "vortgit/providers", name: "vortgit-providers", component: () => import("@/views/vortgit/Providers.vue"), meta: { title: "平台管理" } },
            // 仅管理员
            { path: "contacts", name: "contacts", component: () => import("@/views/contacts/Index.vue"), meta: { title: "组织管理", requiredRole: "admin" } },
            { path: "plugins", name: "plugins", component: () => import("@/views/plugins/Index.vue"), meta: { title: "插件管理", requiredRole: "admin" } },
            { path: "skills", name: "skills", component: () => import("@/views/skills/Index.vue"), meta: { title: "技能管理", requiredRole: "admin" } },
            { path: "channels", name: "channels", component: () => import("@/views/channels/Index.vue"), meta: { title: "通道管理", requiredRole: "admin" } },
            { path: "logs", name: "logs", component: () => import("@/views/logs/Index.vue"), meta: { title: "运行日志", requiredRole: "admin" } },
            { path: "webhooks", name: "webhooks", component: () => import("@/views/webhooks/Index.vue"), meta: { title: "Webhook 管理", requiredRole: "admin" } },
            { path: "agents", name: "agents", component: () => import("@/views/agents/Index.vue"), meta: { title: "Agent 路由", requiredRole: "admin" } },
            { path: "ai-config", name: "ai-config", component: () => import("@/views/ai-config/Index.vue"), meta: { title: "AI 配置", requiredRole: "admin" } },
            { path: "models", redirect: "/ai-config" },
            { path: "settings", redirect: "/ai-config" },
            // 异常页
            { path: "dashboard", redirect: "/overview" },
            { path: "workspace", redirect: "/overview" },
            { path: "exception/403", name: "exception403", component: () => import("@/views/exception/403.vue"), meta: { title: "403" } },
            { path: "exception/404", name: "exception404", component: () => import("@/views/exception/404.vue"), meta: { title: "404" } },
            { path: "exception/500", name: "exception500", component: () => import("@/views/exception/500.vue"), meta: { title: "500" } }
        ]
    },
    { path: "/:pathMatch(.*)*", redirect: "/exception/404" }
];

const router = createRouter({
    history: createWebHistory(),
    routes
});

// 路由守卫
router.beforeEach(async (to, _from, next) => {
    document.title = `${to.meta.title || "OpenVort"} - OpenVort`;

    const userStore = useUserStore();
    const isLoginPage = to.name === "login";

    if (isLoginPage && userStore.token) {
        next("/");
        return;
    }

    if (!isLoginPage && !userStore.token) {
        next("/login");
        return;
    }

    // 首次进入时加载插件路由，注册后重新导航以匹配新增路由
    const pluginStore = usePluginStore();
    if (!isLoginPage && !pluginStore.loaded) {
        await pluginStore.fetchExtensions();
        registerPluginRoutes(pluginStore.extensions);

        // 首次刷新进入插件页面时，会先被 404 重定向。
        // 动态路由注册后，如果原始地址已可匹配，则恢复到原始地址。
        const redirectedFrom = to.redirectedFrom?.fullPath;
        if (redirectedFrom && to.name === "exception404") {
            const resolved = router.resolve(redirectedFrom);
            if (resolved.name && resolved.name !== "exception404") {
                next({ path: redirectedFrom, replace: true });
                return;
            }
        }

        next({ ...to, replace: true });
        return;
    }

    // 角色权限检查
    const requiredRole = to.meta.requiredRole as string | undefined;
    if (requiredRole && !userStore.userInfo.roles.includes(requiredRole)) {
        next("/chat");
        return;
    }

    next();
});

export default router;

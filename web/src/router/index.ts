import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";
import { useUserStore, usePluginStore } from "@/stores";
import { registerPluginRoutes } from "@/router/pluginRoutes";

import vortflowConfig from "@/views/vortflow/plugin";
import vortgitConfig from "@/views/vortgit/plugin";
import jenkinsConfig from "@/views/jenkins/plugin";
import reportsConfig from "@/views/reports/plugin";
import knowledgeConfig from "@/views/knowledge/plugin";
import schedulesConfig from "@/views/schedules/plugin";
import vortsketchConfig from "@/views/vortsketch/plugin";

const BasicLayout = () => import("@/layouts/BasicLayout.vue");
const BlankLayout = () => import("@/layouts/BlankLayout.vue");

const moduleConfigs = [
    vortflowConfig,
    vortgitConfig,
    jenkinsConfig,
    reportsConfig,
    knowledgeConfig,
    schedulesConfig,
    vortsketchConfig,
];

const routes: RouteRecordRaw[] = [
    {
        path: "/login",
        component: BlankLayout,
        children: [{ path: "", name: "login", component: () => import("@/views/login/Index.vue"), meta: { title: "登录" } }]
    },
    {
        path: "/vortsketch/:id",
        component: BlankLayout,
        children: [{ path: "", name: "vortsketch-editor", component: () => import("@/views/vortsketch/Editor.vue"), meta: { title: "原型编辑器" } }]
    },
    {
        path: "/",
        name: "root",
        component: BasicLayout,
        redirect: "/overview",
        children: [
            { path: "chat", name: "chat", component: () => import("@/views/chat/Index.vue"), meta: { title: "AI 助手", fullscreen: true } },
            { path: "overview", name: "overview", component: () => import("@/views/overview/Index.vue"), meta: { title: "概览" } },
            { path: "profile", name: "profile", component: () => import("@/views/profile/Index.vue"), meta: { title: "个人设置" } },
            { path: "notifications", name: "notifications", component: () => import("@/views/notifications/Index.vue"), meta: { title: "通知中心" } },

            // Module routes (from plugin.ts declarations)
            ...moduleConfigs.flatMap(c => c.routes),

            // Admin pages
            { path: "contacts", name: "contacts", component: () => import("@/views/contacts/Index.vue"), meta: { title: "组织管理", requiredRole: "admin" } },
            { path: "plugins", name: "plugins", component: () => import("@/views/plugins/Index.vue"), meta: { title: "插件管理", requiredRole: "admin" } },
            { path: "skills", name: "skills", component: () => import("@/views/skills/Index.vue"), meta: { title: "技能管理", requiredRole: "admin" } },
            { path: "marketplace", name: "marketplace", component: () => import("@/views/marketplace/Index.vue"), meta: { title: "扩展市场", requiredRole: "admin" } },
            { path: "channels", name: "channels", component: () => import("@/views/channels/Index.vue"), meta: { title: "通道管理", requiredRole: "admin" } },
            { path: "logs", name: "logs", component: () => import("@/views/logs/Index.vue"), meta: { title: "运行日志", requiredRole: "admin" } },
            { path: "webhooks", name: "webhooks", component: () => import("@/views/webhooks/Index.vue"), meta: { title: "Webhook 管理", requiredRole: "admin" } },
            { path: "agents", name: "agents", component: () => import("@/views/agents/Index.vue"), meta: { title: "Agent 路由", requiredRole: "admin" } },
            { path: "ai-config", name: "ai-config", component: () => import("@/views/ai-config/Index.vue"), meta: { title: "AI 配置", requiredRole: "admin" } },
            { path: "upgrade", name: "upgrade", component: () => import("@/views/upgrade/Index.vue"), meta: { title: "系统升级", requiredRole: "admin" } },
            { path: "ai-employees", name: "ai-employees", component: () => import("@/views/ai-employees/Index.vue"), meta: { title: "AI 员工", requiredRole: "admin" } },
            { path: "admin/posts", redirect: "/ai-employees" },
            { path: "remote-nodes", name: "remote-nodes", component: () => import("@/views/remote-nodes/Index.vue"), meta: { title: "工作节点", requiredRole: "admin" } },
            { path: "openclaw-nodes", redirect: "/remote-nodes" },
            { path: "models", redirect: "/ai-config" },
            { path: "settings", redirect: "/ai-config" },

            // Legacy redirects & exception pages
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
    routes,
    scrollBehavior(_to, _from, savedPosition) {
        if (savedPosition) {
            return savedPosition;
        }
        return { top: 0 };
    }
});

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

    const pluginStore = usePluginStore();
    if (!isLoginPage && !pluginStore.loaded) {
        await pluginStore.fetchExtensions();
        registerPluginRoutes(pluginStore.extensions);

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

    const requiredRole = to.meta.requiredRole as string | undefined;
    if (requiredRole && !userStore.userInfo.roles.includes(requiredRole)) {
        next("/chat");
        return;
    }

    next();
});

export default router;

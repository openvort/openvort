import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";
import { useUserStore } from "@/stores";

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
        component: BasicLayout,
        redirect: "/chat",
        children: [
            // 所有角色可访问
            { path: "chat", name: "chat", component: () => import("@/views/chat/Index.vue"), meta: { title: "AI 助手", fullscreen: true } },
            { path: "workspace", name: "workspace", component: () => import("@/views/workspace/Index.vue"), meta: { title: "个人工作台" } },
            { path: "dashboard", name: "dashboard", component: () => import("@/views/dashboard/Index.vue"), meta: { title: "仪表盘" } },
            { path: "schedules", name: "schedules", component: () => import("@/views/schedules/Index.vue"), meta: { title: "定时任务" } },
            { path: "profile", name: "profile", component: () => import("@/views/profile/Index.vue"), meta: { title: "个人设置" } },
            // 仅管理员
            { path: "contacts", name: "contacts", component: () => import("@/views/contacts/Index.vue"), meta: { title: "成员管理", requiredRole: "admin" } },
            { path: "plugins", name: "plugins", component: () => import("@/views/plugins/Index.vue"), meta: { title: "插件管理", requiredRole: "admin" } },
            { path: "skills", name: "skills", component: () => import("@/views/skills/Index.vue"), meta: { title: "技能管理", requiredRole: "admin" } },
            { path: "channels", name: "channels", component: () => import("@/views/channels/Index.vue"), meta: { title: "通道管理", requiredRole: "admin" } },
            { path: "logs", name: "logs", component: () => import("@/views/logs/Index.vue"), meta: { title: "运行日志", requiredRole: "admin" } },
            { path: "settings", name: "settings", component: () => import("@/views/settings/Index.vue"), meta: { title: "系统设置", requiredRole: "admin" } },
            // 异常页
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
router.beforeEach((to, _from, next) => {
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

    // 角色权限检查
    const requiredRole = to.meta.requiredRole as string | undefined;
    if (requiredRole && !userStore.userInfo.roles.includes(requiredRole)) {
        next("/chat");
        return;
    }

    next();
});

export default router;

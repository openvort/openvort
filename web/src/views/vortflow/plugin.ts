import type { PluginFrontendConfig } from "@/types/plugin";

export default {
    id: "vortflow",

    routes: [
        {
            path: "vortflow",
            component: () => import("./VortFlowLayout.vue"),
            children: [
                { path: "", redirect: "/vortflow/board" },
                { path: "board", name: "vortflow-board", component: () => import("./Board.vue"), meta: { title: "项目看板" } },
                { path: "stories", name: "vortflow-stories", component: () => import("./Stories.vue"), meta: { title: "需求列表" } },
                { path: "tasks", name: "vortflow-tasks", component: () => import("./TaskTracking.vue"), meta: { title: "任务管理" } },
                { path: "bugs", name: "vortflow-bugs", component: () => import("./Bugs.vue"), meta: { title: "缺陷跟踪" } },
                { path: "iterations", name: "vortflow-iterations", component: () => import("./Iterations.vue"), meta: { title: "迭代管理" } },
                { path: "iterations/:id", name: "vortflow-iteration-detail", component: () => import("./IterationDetail.vue"), meta: { title: "迭代详情" } },
                { path: "versions", name: "vortflow-versions", component: () => import("./Versions.vue"), meta: { title: "版本管理" } },
                { path: "settings", name: "vortflow-settings", component: () => import("./Settings.vue"), meta: { title: "项目设置" } },
                { path: "tag-settings", redirect: "/vortflow/settings" },
                { path: "status-settings", redirect: "/vortflow/settings" },
                { path: "test-cases", name: "vortflow-test-cases", component: () => import("./TestCases.vue"), meta: { title: "测试用例" } },
                { path: "test-plans", name: "vortflow-test-plans", component: () => import("./TestPlans.vue"), meta: { title: "测试计划" } },
                { path: "test-plans/:id", name: "vortflow-test-plan-detail", component: () => import("./TestPlanDetail.vue"), meta: { title: "测试计划详情" } },
                { path: "projects/:id", name: "vortflow-project-detail", component: () => import("./ProjectDetail.vue"), meta: { title: "项目详情" } },
            ],
        },
    ],

    menus: [
        {
            title: "VortFlow", icon: "kanban", label: "研发协作",
            children: [
                { title: "项目看板", icon: "layout-dashboard", path: "/vortflow/board" },
                { title: "需求列表", icon: "list-checks", path: "/vortflow/stories" },
                { title: "任务管理", icon: "check-square", path: "/vortflow/tasks" },
                { title: "缺陷跟踪", icon: "bug", path: "/vortflow/bugs" },
                { title: "迭代管理", icon: "repeat", path: "/vortflow/iterations" },
                { title: "版本管理", icon: "tag", path: "/vortflow/versions" },
                { title: "测试用例", icon: "test-tube", path: "/vortflow/test-cases" },
                { title: "测试计划", icon: "clipboard-check", path: "/vortflow/test-plans" },
                { title: "项目设置", icon: "settings", path: "/vortflow/settings" },
            ],
        },
    ],
} satisfies PluginFrontendConfig;

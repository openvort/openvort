/** 侧边栏菜单配置 */
export interface MenuConfig {
    title: string;
    icon: string;
    path?: string;
    label?: string;
    position?: string;
    requiredRole?: string;
    children?: MenuConfig[];
}

export const menuConfig: MenuConfig[] = [
    { title: "AI 助手", icon: "message-square", path: "/chat" },
    { title: "概览", icon: "home", path: "/overview" },
    {
        title: "VortFlow", icon: "kanban",
        children: [
            { title: "项目看板", icon: "layout-dashboard", path: "/vortflow/board" },
            { title: "需求列表", icon: "list-checks", path: "/vortflow/stories" },
            { title: "任务管理", icon: "check-square", path: "/vortflow/tasks" },
            { title: "缺陷跟踪", icon: "bug", path: "/vortflow/bugs" },
            { title: "里程碑", icon: "milestone", path: "/vortflow/milestones" },
        ],
    },
    {
        title: "VortGit", icon: "git-branch",
        children: [
            { title: "代码仓库", icon: "folder-git-2", path: "/vortgit/repos" },
            { title: "编码任务", icon: "terminal-square", path: "/vortgit/code-tasks" },
            { title: "平台管理", icon: "server", path: "/vortgit/providers" },
        ],
    },
    { title: "定时任务", icon: "clock", path: "/schedules" },
    { title: "汇报中心", icon: "file-bar-chart", path: "/reports" },
    {
        title: "系统管理", icon: "wrench", requiredRole: "admin",
        children: [
            { title: "组织管理", icon: "users", path: "/contacts" },
            { title: "通道管理", icon: "radio", path: "/channels" },
            { title: "Agent 路由", icon: "git-branch", path: "/agents" },
            { title: "模型管理", icon: "cpu", path: "/models" },
            { title: "插件管理", icon: "puzzle", path: "/plugins" },
            { title: "技能管理", icon: "book-open", path: "/skills" },
            { title: "Webhook", icon: "webhook", path: "/webhooks" },
            { title: "运行日志", icon: "file-text", path: "/logs" },
            { title: "系统设置", icon: "settings", path: "/settings" },
        ],
    },
    { title: "个人设置", icon: "user", path: "/profile" },
];

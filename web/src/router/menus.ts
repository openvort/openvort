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
    { title: "AI 助手", icon: "message-square", path: "/chat", position: "top" },
    { title: "通知中心", icon: "bell", path: "/notifications" },
    { title: "概览", icon: "home", path: "/overview" },
    { title: "组织管理", icon: "users", path: "/contacts", label: "团队 & 扩展", requiredRole: "admin" },
    { title: "AI 员工", icon: "bot", path: "/ai-employees", requiredRole: "admin" },
    { title: "计划任务", icon: "clock", path: "/schedules" },
    { title: "汇报中心", icon: "file-bar-chart", path: "/reports" },
    { title: "知识库", icon: "library", path: "/knowledge" },
    { title: "Plugins 插件", icon: "puzzle", path: "/plugins", requiredRole: "admin" },
    { title: "Skills 技能", icon: "book-open", path: "/skills", requiredRole: "admin" },
    { title: "扩展市场", icon: "store", path: "/marketplace", requiredRole: "admin" },
    {
        title: "VortFlow", icon: "kanban", label: "研发协作",
        children: [
            { title: "项目看板", icon: "layout-dashboard", path: "/vortflow/board" },
            { title: "需求列表", icon: "list-checks", path: "/vortflow/stories" },
            { title: "任务管理", icon: "check-square", path: "/vortflow/tasks" },
            { title: "缺陷跟踪", icon: "bug", path: "/vortflow/bugs" },
            { title: "里程碑", icon: "milestone", path: "/vortflow/milestones" },
            { title: "迭代管理", icon: "repeat", path: "/vortflow/iterations" },
            { title: "版本管理", icon: "tag", path: "/vortflow/versions" },
            { title: "测试用例", icon: "test-tube", path: "/vortflow/test-cases" },
            { title: "项目设置", icon: "settings", path: "/vortflow/settings" },
        ],
    },
    {
        title: "VortGit", icon: "git-branch",
        children: [
            { title: "代码仓库", icon: "folder-git-2", path: "/vortgit/repos" },
            { title: "编码任务", icon: "terminal-square", path: "/vortgit/code-tasks" },
        ],
    },
    {
        title: "系统管理", icon: "wrench", label: "系统", requiredRole: "admin",
        children: [
            { title: "通道管理", icon: "radio", path: "/channels" },
            { title: "Agent 路由", icon: "git-branch", path: "/agents" },
            { title: "AI 配置", icon: "sparkles", path: "/ai-config" },
            { title: "Git 平台", icon: "server", path: "/vortgit/providers" },
            { title: "Webhook", icon: "webhook", path: "/webhooks" },
            { title: "工作节点", icon: "cpu", path: "/remote-nodes" },
            { title: "系统升级", icon: "arrow-up-circle", path: "/upgrade" },
            { title: "运行日志", icon: "file-text", path: "/logs" },
        ],
    },
    { title: "个人设置", icon: "user", path: "/profile", position: "bottom" },
];

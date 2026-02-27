/** 侧边栏菜单配置 */
export interface MenuConfig {
    title: string;
    icon: string;
    path?: string;
    requiredRole?: string;  // 需要的角色，不填则所有人可见
    children?: MenuConfig[];
}

export const menuConfig: MenuConfig[] = [
    { title: "AI 助手", icon: "message-square", path: "/chat" },
    { title: "个人工作台", icon: "home", path: "/workspace" },
    { title: "仪表盘", icon: "bar-chart-2", path: "/dashboard" },
    { title: "定时任务", icon: "clock", path: "/schedules" },
    { title: "成员管理", icon: "users", path: "/contacts", requiredRole: "admin" },
    { title: "插件管理", icon: "puzzle", path: "/plugins", requiredRole: "admin" },
    { title: "技能管理", icon: "book-open", path: "/skills", requiredRole: "admin" },
    { title: "通道管理", icon: "radio", path: "/channels", requiredRole: "admin" },
    { title: "运行日志", icon: "file-text", path: "/logs", requiredRole: "admin" },
    { title: "系统设置", icon: "settings", path: "/settings", requiredRole: "admin" },
    { title: "个人设置", icon: "user", path: "/profile" }
];

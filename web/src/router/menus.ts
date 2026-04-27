import vortflowConfig from "@/views/vortflow/plugin";
import vortgitConfig from "@/views/vortgit/plugin";
import jenkinsConfig from "@/views/jenkins/plugin";
import reportsConfig from "@/views/reports/plugin";
import knowledgeConfig from "@/views/knowledge/plugin";
import schedulesConfig from "@/views/schedules/plugin";
import vortsketchConfig from "@/views/vortsketch/plugin";
import vortcertConfig from "@/views/vortcert/plugin";

/** 侧边栏菜单配置 */
export interface MenuConfig {
    title: string;
    icon: string;
    path?: string;
    externalUrl?: string;
    label?: string;
    position?: string;
    requiredRole?: string;
    children?: MenuConfig[];
}

export const menuConfig: MenuConfig[] = [
    { title: "AI 助手", icon: "message-square", path: "/chat", position: "top" },
    { title: "工作台", icon: "home", path: "/overview" },
    { title: "AI 员工", icon: "bot", path: "/ai-employees", label: "AI 能力", requiredRole: "admin" },
    ...knowledgeConfig.menus,
    { title: "技能管理", icon: "book-open", path: "/skills", requiredRole: "admin" },
    ...vortflowConfig.menus,
    ...vortgitConfig.menus,
    ...jenkinsConfig.menus,
    ...vortsketchConfig.menus,
    ...vortcertConfig.menus,
    { title: "组织管理", icon: "users", path: "/contacts", label: "团队效率", requiredRole: "admin" },
    ...reportsConfig.menus,
    ...schedulesConfig.menus,
    {
        title: "扩展管理", icon: "blocks", label: "系统", requiredRole: "admin",
        children: [
            { title: "插件管理", icon: "puzzle", path: "/plugins" },
            { title: "扩展市场", icon: "store", path: "/marketplace" },
        ],
    },
    {
        title: "系统管理", icon: "wrench", requiredRole: "admin",
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
    {
        title: "资源", icon: "book-marked",
        children: [
            { title: "文档", icon: "file-text", externalUrl: "https://www.openvort.com/docs" },
            { title: "社区", icon: "users", externalUrl: "https://www.openvort.com/community" },
        ],
    },
    { title: "个人设置", icon: "user", path: "/profile", position: "bottom" },
];

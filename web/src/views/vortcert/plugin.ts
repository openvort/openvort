import type { PluginFrontendConfig } from "@/types/plugin";

export default {
    id: "vortcert",

    routes: [
        { path: "vortcert/overview", name: "vortcert-overview", component: () => import("./Overview.vue"), meta: { title: "证书总览" } },
        { path: "vortcert/domains", name: "vortcert-domains", component: () => import("./Domains.vue"), meta: { title: "域名管理" } },
        { path: "vortcert/dns-providers", name: "vortcert-dns-providers", component: () => import("./DnsProviders.vue"), meta: { title: "DNS 配置" } },
        { path: "vortcert/deploy-targets", name: "vortcert-deploy-targets", component: () => import("./DeployTargets.vue"), meta: { title: "部署目标" } },
    ],

    menus: [
        {
            title: "VortCert", icon: "shield-check",
            children: [
                { title: "证书总览", icon: "shield-check", path: "/vortcert/overview" },
                { title: "域名管理", icon: "globe", path: "/vortcert/domains" },
                { title: "DNS 配置", icon: "server", path: "/vortcert/dns-providers" },
                { title: "部署目标", icon: "rocket", path: "/vortcert/deploy-targets" },
            ],
        },
    ],
} satisfies PluginFrontendConfig;

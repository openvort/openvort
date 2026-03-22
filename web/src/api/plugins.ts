import request from "@/utils/request";

// ---- Plugins ----

export function getPlugins() {
    return request.get("/admin/plugins");
}

export function getPluginDetail(name: string) {
    return request.get(`/admin/plugins/${name}`);
}

export function updatePlugin(name: string, config: Record<string, any>) {
    return request.put(`/admin/plugins/${name}`, { config });
}

export function installPlugin(name: string) {
    return request.post(`/admin/plugins/${name}/install`);
}

export function uninstallPlugin(name: string) {
    return request.post(`/admin/plugins/${name}/uninstall`);
}

export function pipInstallPlugin(packageName: string) {
    return request.post("/admin/plugins/install", { package_name: packageName });
}

export function uploadPlugin(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return request.post("/admin/plugins/upload", formData);
}

export function deletePlugin(name: string) {
    return request.delete(`/admin/plugins/${name}`);
}

// ---- Marketplace ----

export function marketplaceSearch(params: { query?: string; type?: string; category?: string; sort?: string; page?: number; limit?: number }) {
    return request.get("/admin/marketplace/search", { params });
}

export function marketplaceGetDetail(slug: string, author: string = "") {
    return request.get(`/admin/marketplace/detail/${slug}`, { params: author ? { author } : {} });
}

export function marketplaceInstallSkill(slug: string, author: string = "") {
    return request.post("/admin/marketplace/install/skill", { slug, author });
}

export function marketplaceInstallPlugin(slug: string, author: string = "") {
    return request.post("/admin/marketplace/install/plugin", { slug, author });
}

export function marketplaceListInstalled() {
    return request.get("/admin/marketplace/installed");
}

export function marketplaceUninstall(slug: string, type: string = "skill") {
    return request.post("/admin/marketplace/uninstall", { slug, type });
}

export function marketplaceCheckUpdates() {
    return request.get("/admin/marketplace/updates");
}

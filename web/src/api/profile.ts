import request from "@/utils/request";

export function getProfile() {
    return request.get("/me/profile");
}

export function uploadAvatar(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return request.post("/me/profile/avatar", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 30000,
    });
}

export function uploadMemberAvatar(memberId: string, file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return request.post(`/admin/members/${memberId}/avatar`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 30000,
    });
}

export function updateProfile(data: { name?: string; email?: string; phone?: string; position?: string; department?: string; bio?: string }) {
    return request.put("/me/profile", data);
}

export function changePassword(old_password: string, new_password: string) {
    return request.put("/me/password", { old_password, new_password });
}

export function getNotificationPrefs() {
    return request.get("/me/notifications");
}

export function updateNotificationPrefs(preferences: Record<string, Record<string, boolean>>) {
    return request.put("/me/notifications", { preferences });
}

export function getGitTokens() {
    return request.get("/me/git-tokens");
}

export function saveGitToken(platform: string, token: string, username: string = "") {
    return request.put("/me/git-tokens", { platform, token, username });
}

export function deleteGitToken(platform: string) {
    return request.delete(`/me/git-tokens/${platform}`);
}

export function getPluginPersonalSettings() {
    return request.get("/me/plugin-settings");
}

export function getPluginPersonalSetting(pluginName: string) {
    return request.get(`/me/plugin-settings/${pluginName}`);
}

export function savePluginPersonalSetting(pluginName: string, settings: Record<string, any>) {
    return request.put(`/me/plugin-settings/${pluginName}`, { settings });
}

export function deletePluginPersonalSetting(pluginName: string) {
    return request.delete(`/me/plugin-settings/${pluginName}`);
}

export function getEnabledChannels() {
    return request.get("/admin/channels");
}

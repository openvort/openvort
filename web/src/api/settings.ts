import request from "@/utils/request";

// ---- Channels ----

export function getChannels() {
    return request.get("/admin/channels");
}

export function getChannelDetail(name: string) {
    return request.get(`/admin/channels/${name}`);
}

export function updateChannel(name: string, config: Record<string, any>) {
    return request.put(`/admin/channels/${name}`, { config });
}

export function toggleChannel(name: string) {
    return request.post(`/admin/channels/${name}/toggle`);
}

export function testChannel(name: string) {
    return request.post(`/admin/channels/${name}/test`);
}

// ---- Logs ----

export function getLogs(params?: { page?: number; size?: number; level?: string; keyword?: string }) {
    return request.get("/admin/logs", { params });
}

// ---- AI Models ----

export function getModels() {
    return request.get("/admin/models");
}

export function createModel(data: {
    name: string;
    provider: string;
    model: string;
    api_key?: string;
    api_base?: string;
    max_tokens?: number;
    timeout?: number;
    enabled?: boolean;
    api_format?: string;
}) {
    return request.post("/admin/models", data);
}

export function updateModel(modelId: string, data: {
    name?: string;
    provider?: string;
    model?: string;
    api_key?: string;
    api_base?: string;
    max_tokens?: number;
    timeout?: number;
    enabled?: boolean;
    api_format?: string;
}) {
    return request.put(`/admin/models/${modelId}`, data);
}

export function deleteModel(modelId: string) {
    return request.delete(`/admin/models/${modelId}`);
}

export function testModel(modelId: string) {
    return request.post(`/admin/models/${modelId}/test`);
}

export function fetchAvailableModels(data: { provider: string; api_key: string; api_base: string; model_id?: string }) {
    return request.post("/admin/models/fetch-available", data);
}

export function batchTestModels() {
    return request.post("/admin/models/batch-test");
}

// ---- Voice Providers ----

export function getVoiceProviders() {
    return request.get("/admin/voice-providers");
}

export function createVoiceProvider(data: {
    name: string;
    platform: string;
    api_key?: string;
    config?: Record<string, any>;
    is_default?: boolean;
}) {
    return request.post("/admin/voice-providers", data);
}

export function updateVoiceProvider(providerId: string, data: {
    name?: string;
    api_key?: string;
    config?: Record<string, any>;
    is_default?: boolean;
    is_enabled?: boolean;
}) {
    return request.put(`/admin/voice-providers/${providerId}`, data);
}

export function deleteVoiceProvider(providerId: string) {
    return request.delete(`/admin/voice-providers/${providerId}`);
}

// ---- System Settings ----

export function getSettings() {
    return request.get("/admin/settings");
}

export function updateSettings(data: Record<string, any>) {
    return request.put("/admin/settings", data);
}

export function restartService() {
    return request.post("/admin/settings/restart");
}

export function getCliTools() {
    return request.get("/admin/settings/cli-tools");
}

export function getCliToolInstallUrl(toolName: string, token: string) {
    return `/api/admin/settings/cli-tools/${toolName}/install?token=${encodeURIComponent(token)}`;
}

export function getCliToolUninstallUrl(toolName: string, token: string) {
    return `/api/admin/settings/cli-tools/${toolName}/uninstall?token=${encodeURIComponent(token)}`;
}

// ---- Upgrade & Backup ----

export function checkUpgrade(force?: boolean) {
    return request.get("/admin/upgrade/check", { params: force ? { force: true } : undefined });
}

export function getReleases(perPage = 20) {
    return request.get("/admin/upgrade/releases", { params: { per_page: perPage } });
}

export function getUpgradeStreamUrl(version: string, token: string) {
    return `/api/admin/upgrade/apply?token=${encodeURIComponent(token)}`;
}

export function getBackups() {
    return request.get("/admin/upgrade/backups");
}

export function createBackup() {
    return request.post("/admin/upgrade/backups");
}

export function getBackupDownloadUrl(filename: string, token: string) {
    return `/api/admin/upgrade/backups/${encodeURIComponent(filename)}?token=${encodeURIComponent(token)}`;
}

export function deleteBackup(filename: string) {
    return request.delete(`/admin/upgrade/backups/${encodeURIComponent(filename)}`);
}

export function getRestoreStreamUrl(filename: string, token: string) {
    return `/api/admin/upgrade/backups/${encodeURIComponent(filename)}/restore?token=${encodeURIComponent(token)}`;
}

// ---- Webhooks ----

export function getWebhooks() {
    return request.get("/admin/webhooks");
}

export function getWebhookPresets() {
    return request.get("/admin/webhooks/presets");
}

export function getWebhookPresetDetail(presetId: string) {
    return request.get(`/admin/webhooks/presets/${presetId}`);
}

export function installWebhookPreset(presetId: string, data?: { secret?: string; member_id?: string; name?: string }) {
    return request.post(`/admin/webhooks/presets/${presetId}/install`, data || {});
}

export function createWebhook(data: {
    name: string;
    secret?: string;
    action_type?: string;
    prompt_template?: string;
    channel?: string;
    user_id?: string;
    member_id?: string;
}) {
    return request.post("/admin/webhooks", data);
}

export function updateWebhook(name: string, data: Record<string, any>) {
    return request.put(`/admin/webhooks/${name}`, data);
}

export function deleteWebhook(name: string) {
    return request.delete(`/admin/webhooks/${name}`);
}

// ---- Agent Routes ----

export function getAgentRoutes() {
    return request.get("/admin/agents");
}

export function createAgentRoute(data: {
    name: string;
    model?: string;
    system_prompt?: string;
    max_tokens?: number;
    channels?: string[];
    user_ids?: string[];
    group_ids?: string[];
}) {
    return request.post("/admin/agents", data);
}

export function deleteAgentRoute(name: string) {
    return request.delete(`/admin/agents/${name}`);
}

// ---- Remote Nodes ----

export function getRemoteNodes() {
    return request.get("/admin/remote-nodes");
}

export function createRemoteNode(data: {
    name: string; node_type?: string;
    gateway_url?: string; gateway_token?: string;
    image?: string; memory_limit?: string; cpu_limit?: number;
    network_mode?: string; env_vars?: Record<string, string>;
    description?: string;
}) {
    return request.post("/admin/remote-nodes", data);
}

export function updateRemoteNode(nodeId: string, data: {
    name?: string; gateway_url?: string; gateway_token?: string;
    description?: string; node_type?: string; config?: Record<string, any>;
}) {
    return request.put(`/admin/remote-nodes/${nodeId}`, data);
}

export function deleteRemoteNode(nodeId: string) {
    return request.delete(`/admin/remote-nodes/${nodeId}`);
}

export function testRemoteNode(nodeId: string) {
    return request.post(`/admin/remote-nodes/${nodeId}/test`);
}

export function getRemoteNodeMembers(nodeId: string) {
    return request.get(`/admin/remote-nodes/${nodeId}/members`);
}

export function startDockerContainer(nodeId: string) {
    return request.post(`/admin/remote-nodes/${nodeId}/start`);
}

export function stopDockerContainer(nodeId: string) {
    return request.post(`/admin/remote-nodes/${nodeId}/stop`);
}

export function restartDockerContainer(nodeId: string) {
    return request.post(`/admin/remote-nodes/${nodeId}/restart`);
}

export function getContainerStatus(nodeId: string) {
    return request.get(`/admin/remote-nodes/${nodeId}/container-status`);
}

export function getContainerStats(nodeId: string) {
    return request.get(`/admin/remote-nodes/${nodeId}/container-stats`);
}

export function getContainerLogs(nodeId: string, tail: number = 100) {
    return request.get(`/admin/remote-nodes/${nodeId}/logs`, { params: { tail } });
}

export function listDockerImages() {
    return request.get("/admin/remote-nodes/docker/images");
}

export function pullDockerImage(image: string) {
    return request.post("/admin/remote-nodes/docker/pull-image", { image });
}

export function checkImageStatus(images: string[]) {
    return request.get("/admin/remote-nodes/docker/image-status", { params: { images: images.join(",") } });
}

export function getInstallImageUrl(token: string) {
    return `/api/admin/remote-nodes/docker/install-image?token=${encodeURIComponent(token)}`;
}

export function getAllDockerStats() {
    return request.get("/admin/remote-nodes/docker/stats");
}

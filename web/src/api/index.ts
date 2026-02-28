import request from "@/utils/request";

/** 登录 */
export function login(user_id: string, password: string) {
    return request.post("/auth/login", { user_id, password });
}

/** 获取当前用户信息 */
export function getProfile() {
    return request.get("/me/profile");
}

/** 上传头像 */
export function uploadAvatar(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return request.post("/me/profile/avatar", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 30000,
    });
}

/** 更新个人资料 */
export function updateProfile(data: { name?: string; email?: string; phone?: string; position?: string; department?: string; bio?: string }) {
    return request.put("/me/profile", data);
}

/** 修改密码 */
export function changePassword(old_password: string, new_password: string) {
    return request.put("/me/password", { old_password, new_password });
}

/** 获取通知偏好 */
export function getNotificationPrefs() {
    return request.get("/me/notifications");
}

/** 更新通知偏好 */
export function updateNotificationPrefs(preferences: Record<string, Record<string, boolean>>) {
    return request.put("/me/notifications", { preferences });
}

/** 获取通道列表（用于通知设置等） */
export function getEnabledChannels() {
    return request.get("/admin/channels");
}

/** 获取聊天历史 */
export function getChatHistory(limit = 50, sessionId = "default") {
    return request.get("/chat/history", { params: { limit, session_id: sessionId } });
}

/** 发送聊天消息，返回 message_id */
export function sendChatMessage(
    content: string,
    images: { data: string; media_type: string }[] = [],
    sessionId = "default"
) {
    return request.post("/chat/send", { content, images, session_id: sessionId });
}

/** 获取 SSE 流式地址 */
export function getChatStreamUrl(messageId: string, token: string) {
    return `/api/chat/stream/${messageId}?token=${encodeURIComponent(token)}`;
}

/** 获取会话信息（token 用量、thinking 级别） */
export function getChatSessionInfo(sessionId = "default") {
    return request.get("/chat/session-info", { params: { session_id: sessionId } });
}

/** 设置 thinking 级别 */
export function setChatThinking(level: string, sessionId = "default") {
    return request.post("/chat/thinking", { level, session_id: sessionId });
}

/** 压缩会话上下文 */
export function compactChatSession(sessionId = "default") {
    return request.post("/chat/compact", { session_id: sessionId });
}

/** 重置会话 */
export function resetChatSession(sessionId = "default") {
    return request.post("/chat/reset", { session_id: sessionId });
}

/** 搜索成员（@mention 提示） */
export function getChatMembers(keyword = "", limit = 20) {
    return request.get("/chat/members", { params: { keyword, limit } });
}

// ---- 对话管理 ----

/** 对话列表 */
export function getChatSessions() {
    return request.get("/chat/sessions");
}

/** 新建对话 */
export function createChatSession(title = "新对话") {
    return request.post("/chat/sessions", { title });
}

/** 重命名对话 */
export function renameChatSession(sessionId: string, title: string) {
    return request.put(`/chat/sessions/${sessionId}`, { title });
}

/** 删除对话 */
export function deleteChatSession(sessionId: string) {
    return request.delete(`/chat/sessions/${sessionId}`);
}

/** 批量删除对话 */
export function batchDeleteChatSessions(sessionIds: string[]) {
    return request.post("/chat/sessions/batch-delete", { session_ids: sessionIds });
}

/** 健康检查（版本号 + LLM 状态） */
export function getHealthStatus() {
    return request.get("/health");
}

/** 仪表盘数据 */
export function getDashboard() {
    return request.get("/dashboard");
}

// ---- 管理员 API（/api/admin/ 前缀）----

// -- 成员管理 --

/** 成员列表 */
export function getMembers(params?: { search?: string; role?: string; page?: number; size?: number }) {
    return request.get("/admin/members", { params });
}

/** 成员详情 */
export function getMember(id: string) {
    return request.get(`/admin/members/${id}`);
}

/** 编辑成员 */
export function updateMember(id: string, data: { name?: string; email?: string; phone?: string; status?: string; is_account?: boolean }) {
    return request.put(`/admin/members/${id}`, data);
}

/** 重置密码 */
export function resetMemberPassword(id: string, password?: string) {
    return request.post(`/admin/members/${id}/reset-password`, { password });
}

/** 启用/禁用登录 */
export function toggleMemberAccount(id: string) {
    return request.post(`/admin/members/${id}/toggle-account`);
}

/** 分配角色 */
export function assignMemberRole(id: string, role: string) {
    return request.post(`/admin/members/${id}/roles`, { role });
}

/** 移除角色 */
export function removeMemberRole(id: string, role: string) {
    return request.delete(`/admin/members/${id}/roles/${role}`);
}

/** 删除成员 */
export function deleteMember(id: string) {
    return request.delete(`/admin/members/${id}`);
}

/** 批量删除 */
export function batchDeleteMembers(ids: string[]) {
    return request.post("/admin/members/batch/delete", { ids });
}

/** 批量启用登录 */
export function batchEnableAccount(ids: string[]) {
    return request.post("/admin/members/batch/enable-account", { ids });
}

/** 批量禁用登录 */
export function batchDisableAccount(ids: string[]) {
    return request.post("/admin/members/batch/disable-account", { ids });
}

/** 批量分配角色 */
export function batchAssignRole(ids: string[], role: string) {
    return request.post("/admin/members/batch/assign-role", { ids, role });
}

/** 批量移除角色 */
export function batchRemoveRole(ids: string[], role: string) {
    return request.post("/admin/members/batch/remove-role", { ids, role });
}

/** 批量分配部门 */
export function batchAssignDept(ids: string[], deptId: number) {
    return request.post("/admin/members/batch/assign-dept", { ids, dept_id: deptId });
}

/** 批量移除部门 */
export function batchRemoveDept(ids: string[], deptId: number) {
    return request.post("/admin/members/batch/remove-dept", { ids, dept_id: deptId });
}

/** 角色列表 */
export function getRoles() {
    return request.get("/admin/members/roles/list");
}

/** 权限列表 */
export function getPermissions() {
    return request.get("/admin/members/permissions/list");
}

/** 创建角色 */
export function createRole(data: { name: string; display_name: string; permissions: string[] }) {
    return request.post("/admin/members/roles", data);
}

/** 更新角色 */
export function updateRole(roleId: number, data: { display_name?: string; permissions?: string[] }) {
    return request.put(`/admin/members/roles/${roleId}`, data);
}

/** 删除角色 */
export function deleteRole(roleId: number) {
    return request.delete(`/admin/members/roles/${roleId}`);
}

// -- 联系人（同步/匹配）--

/** 联系人列表 */
export function getContacts() {
    return request.get("/admin/contacts");
}

/** 同步联系人 */
export function syncContacts(channel?: string) {
    return request.post("/admin/contacts/sync", null, { params: channel ? { channel } : {} });
}

/** 获取待合并建议 */
export function getSuggestions() {
    return request.get("/admin/contacts/suggestions");
}

/** 接受合并建议 */
export function acceptSuggestion(id: number) {
    return request.post(`/admin/contacts/suggestions/${id}/accept`);
}

/** 拒绝合并建议 */
export function rejectSuggestion(id: number) {
    return request.post(`/admin/contacts/suggestions/${id}/reject`);
}

/** 手动合并成员 */
export function mergeMembers(source_id: string, target_id: string) {
    return request.post("/admin/contacts/merge", { source_id, target_id });
}

/** 去重扫描 */
export function dedupContacts() {
    return request.post("/admin/contacts/dedup");
}

// -- 部门管理 --

/** 部门树 */
export function getDepartmentTree(platform?: string) {
    return request.get("/admin/departments", { params: { platform } });
}

/** 部门详情 */
export function getDepartment(id: number) {
    return request.get(`/admin/departments/${id}`);
}

/** 创建部门 */
export function createDepartment(name: string, parent_id?: number | null) {
    return request.post("/admin/departments", { name, parent_id });
}

/** 编辑部门 */
export function updateDepartment(id: number, data: { name?: string; parent_id?: number | null; order?: number }) {
    return request.put(`/admin/departments/${id}`, data);
}

/** 删除部门 */
export function deleteDepartment(id: number) {
    return request.delete(`/admin/departments/${id}`);
}

/** 部门成员列表 */
export function getDepartmentMembers(id: number) {
    return request.get(`/admin/departments/${id}/members`);
}

/** 添加成员到部门 */
export function addDepartmentMember(deptId: number, memberId: string, isPrimary = false) {
    return request.post(`/admin/departments/${deptId}/members`, { member_id: memberId, is_primary: isPrimary });
}

/** 移除部门成员 */
export function removeDepartmentMember(deptId: number, memberId: string) {
    return request.delete(`/admin/departments/${deptId}/members/${memberId}`);
}

/** 插件列表 */
export function getPlugins() {
    return request.get("/admin/plugins");
}

/** 插件详情 */
export function getPluginDetail(name: string) {
    return request.get(`/admin/plugins/${name}`);
}

/** 更新插件配置 */
export function updatePlugin(name: string, config: Record<string, any>) {
    return request.put(`/admin/plugins/${name}`, { config });
}

/** 启用/禁用插件 */
export function togglePlugin(name: string) {
    return request.post(`/admin/plugins/${name}/toggle`);
}

/** pip 安装插件 */
export function installPlugin(packageName: string) {
    return request.post("/admin/plugins/install", { package_name: packageName });
}

/** 上传本地插件 zip */
export function uploadPlugin(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return request.post("/admin/plugins/upload", formData);
}

/** 删除本地插件 */
export function deletePlugin(name: string) {
    return request.delete(`/admin/plugins/${name}`);
}

/** 通道列表 */
export function getChannels() {
    return request.get("/admin/channels");
}

/** 通道详情 */
export function getChannelDetail(name: string) {
    return request.get(`/admin/channels/${name}`);
}

/** 更新通道配置 */
export function updateChannel(name: string, config: Record<string, any>) {
    return request.put(`/admin/channels/${name}`, { config });
}

/** 启用/禁用通道 */
export function toggleChannel(name: string) {
    return request.post(`/admin/channels/${name}/toggle`);
}

/** 测试通道连接 */
export function testChannel(name: string) {
    return request.post(`/admin/channels/${name}/test`);
}

/** 运行日志 */
export function getLogs(params?: { page?: number; size?: number; level?: string; keyword?: string }) {
    return request.get("/admin/logs", { params });
}

/** 模型列表 */
export function getModels() {
    return request.get("/admin/models");
}

/** 新增模型 */
export function createModel(data: {
    name: string;
    provider: string;
    model: string;
    api_key?: string;
    api_base?: string;
    max_tokens?: number;
    timeout?: number;
    enabled?: boolean;
}) {
    return request.post("/admin/models", data);
}

/** 更新模型 */
export function updateModel(modelId: string, data: {
    name?: string;
    provider?: string;
    model?: string;
    api_key?: string;
    api_base?: string;
    max_tokens?: number;
    timeout?: number;
    enabled?: boolean;
}) {
    return request.put(`/admin/models/${modelId}`, data);
}

/** 删除模型 */
export function deleteModel(modelId: string) {
    return request.delete(`/admin/models/${modelId}`);
}

/** 获取系统设置 */
export function getSettings() {
    return request.get("/admin/settings");
}

/** 更新系统设置 */
export function updateSettings(data: Record<string, any>) {
    return request.put("/admin/settings", data);
}

/** 重启后端服务 */
export function restartService() {
    return request.post("/admin/settings/restart");
}

// ---- 定时任务（个人）----

/** 我的任务列表 */
export function getMySchedules() {
    return request.get("/schedules");
}

/** 创建个人任务 */
export function createMySchedule(data: {
    name: string;
    description?: string;
    schedule_type: string;
    schedule: string;
    timezone?: string;
    action_type?: string;
    action_config?: Record<string, any>;
    enabled?: boolean;
}) {
    return request.post("/schedules", data);
}

/** 编辑个人任务 */
export function updateMySchedule(jobId: string, data: Record<string, any>) {
    return request.put(`/schedules/${jobId}`, data);
}

/** 删除个人任务 */
export function deleteMySchedule(jobId: string) {
    return request.delete(`/schedules/${jobId}`);
}

/** 启用/禁用个人任务 */
export function toggleMySchedule(jobId: string) {
    return request.post(`/schedules/${jobId}/toggle`);
}

/** 立即执行个人任务 */
export function runMySchedule(jobId: string) {
    return request.post(`/schedules/${jobId}/run`);
}

// ---- 定时任务（管理员）----

/** 所有任务列表 */
export function getAdminSchedules() {
    return request.get("/admin/schedules");
}

/** 创建团队任务 */
export function createAdminSchedule(data: {
    name: string;
    description?: string;
    schedule_type: string;
    schedule: string;
    timezone?: string;
    action_type?: string;
    action_config?: Record<string, any>;
    enabled?: boolean;
}) {
    return request.post("/admin/schedules", data);
}

/** 编辑任意任务 */
export function updateAdminSchedule(jobId: string, data: Record<string, any>) {
    return request.put(`/admin/schedules/${jobId}`, data);
}

/** 删除任意任务 */
export function deleteAdminSchedule(jobId: string) {
    return request.delete(`/admin/schedules/${jobId}`);
}

/** 启用/禁用任意任务 */
export function toggleAdminSchedule(jobId: string) {
    return request.post(`/admin/schedules/${jobId}/toggle`);
}

/** 立即执行任意任务 */
export function runAdminSchedule(jobId: string) {
    return request.post(`/admin/schedules/${jobId}/run`);
}

// ---- Skill 管理（管理员）----

/** Skill 列表 */
export function getSkills() {
    return request.get("/admin/skills");
}

/** Skill 详情 */
export function getSkill(name: string) {
    return request.get(`/admin/skills/${name}`);
}

/** 创建 Skill */
export function createSkill(data: { name: string; description?: string; content?: string }) {
    return request.post("/admin/skills", data);
}

/** 更新 Skill */
export function updateSkill(name: string, data: { description?: string; content?: string }) {
    return request.put(`/admin/skills/${name}`, data);
}

/** 删除 Skill */
export function deleteSkill(name: string) {
    return request.delete(`/admin/skills/${name}`);
}

/** 启用/禁用 Skill */
export function toggleSkill(name: string) {
    return request.post(`/admin/skills/${name}/toggle`);
}

// ---- Webhook 管理（管理员）----

/** Webhook 列表 */
export function getWebhooks() {
    return request.get("/admin/webhooks");
}

/** 创建 Webhook */
export function createWebhook(data: {
    name: string;
    secret?: string;
    action_type?: string;
    prompt_template?: string;
    channel?: string;
    user_id?: string;
}) {
    return request.post("/admin/webhooks", data);
}

/** 更新 Webhook */
export function updateWebhook(name: string, data: Record<string, any>) {
    return request.put(`/admin/webhooks/${name}`, data);
}

/** 删除 Webhook */
export function deleteWebhook(name: string) {
    return request.delete(`/admin/webhooks/${name}`);
}

// ---- Agent 路由管理（管理员）----

/** Agent 路由列表 */
export function getAgentRoutes() {
    return request.get("/admin/agents");
}

/** 创建 Agent 路由 */
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

/** 删除 Agent 路由 */
export function deleteAgentRoute(name: string) {
    return request.delete(`/admin/agents/${name}`);
}

// ---- VortFlow ----

/** VortFlow 看板统计 */
export function getVortflowStats() {
    return request.get("/vortflow/dashboard/stats");
}

/** VortFlow 项目列表 */
export function getVortflowProjects() {
    return request.get("/vortflow/projects");
}

/** VortFlow 需求列表 */
export function getVortflowStories(params: { state?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/stories", { params });
}

/** VortFlow 任务列表 */
export function getVortflowTasks(params: { state?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/tasks", { params });
}

/** VortFlow 缺陷列表 */
export function getVortflowBugs(params: { state?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/bugs", { params });
}

/** VortFlow 里程碑列表 */
export function getVortflowMilestones(params: { page?: number; page_size?: number }) {
    return request.get("/vortflow/milestones", { params });
}

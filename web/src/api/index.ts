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

// -- 汇报关系 --

/** 汇报关系列表 */
export function getReportingRelations(memberId?: string) {
    return request.get("/admin/reporting-relations", { params: { member_id: memberId } });
}

/** 创建汇报关系 */
export function createReportingRelation(data: { reporter_id: string; supervisor_id: string; relation_type?: string; is_primary?: boolean }) {
    return request.post("/admin/reporting-relations", data);
}

/** 更新汇报关系 */
export function updateReportingRelation(id: number, data: { relation_type?: string; is_primary?: boolean }) {
    return request.put(`/admin/reporting-relations/${id}`, data);
}

/** 删除汇报关系 */
export function deleteReportingRelation(id: number) {
    return request.delete(`/admin/reporting-relations/${id}`);
}

/** 获取下属 */
export function getSubordinates(memberId: string) {
    return request.get(`/admin/reporting-relations/subordinates/${memberId}`);
}

/** 获取上级 */
export function getSupervisors(memberId: string) {
    return request.get(`/admin/reporting-relations/supervisors/${memberId}`);
}

// -- 企业日历 --

/** 企业日历列表 */
export function getOrgCalendar(year?: number) {
    return request.get("/admin/org-calendar", { params: { year } });
}

/** 新增日历条目 */
export function createOrgCalendarEntry(data: { date: string; day_type: string; name?: string }) {
    return request.post("/admin/org-calendar", data);
}

/** 批量导入日历条目 */
export function batchCreateOrgCalendar(entries: { date: string; day_type: string; name?: string }[]) {
    return request.post("/admin/org-calendar/batch", { entries });
}

/** 删除日历条目 */
export function deleteOrgCalendarEntry(id: number) {
    return request.delete(`/admin/org-calendar/${id}`);
}

/** 同步法定节假日 */
export function syncHolidays(year?: number) {
    return request.post("/admin/org-calendar/sync-holidays", null, { params: { year } });
}

/** 获取工时设置 */
export function getWorkSettings() {
    return request.get("/admin/org-calendar/work-settings");
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

/** 测试模型连通性 */
export function testModel(modelId: string) {
    return request.post(`/admin/models/${modelId}/test`);
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

/** Webhook 预置模板列表 */
export function getWebhookPresets() {
    return request.get("/admin/webhooks/presets");
}

/** 预置模板详情 */
export function getWebhookPresetDetail(presetId: string) {
    return request.get(`/admin/webhooks/presets/${presetId}`);
}

/** 一键安装预置模板 */
export function installWebhookPreset(presetId: string, secret?: string) {
    return request.post(`/admin/webhooks/presets/${presetId}/install`, null, {
        params: secret ? { secret } : {},
    });
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
export function getVortflowStats(project_id?: string) {
    return request.get("/vortflow/dashboard/stats", { params: project_id ? { project_id } : {} });
}

// -- 项目 --

/** VortFlow 项目列表 */
export function getVortflowProjects() {
    return request.get("/vortflow/projects");
}

/** VortFlow 项目详情 */
export function getVortflowProject(id: string) {
    return request.get(`/vortflow/projects/${id}`);
}

/** VortFlow 创建项目 */
export function createVortflowProject(data: { name: string; description?: string; product?: string; iteration?: string; version?: string; start_date?: string; end_date?: string }) {
    return request.post("/vortflow/projects", data);
}

/** VortFlow 更新项目 */
export function updateVortflowProject(id: string, data: { name?: string; description?: string; product?: string; iteration?: string; version?: string; start_date?: string; end_date?: string }) {
    return request.put(`/vortflow/projects/${id}`, data);
}

/** VortFlow 删除项目 */
export function deleteVortflowProject(id: string) {
    return request.delete(`/vortflow/projects/${id}`);
}

/** VortFlow 项目成员列表 */
export function getVortflowProjectMembers(projectId: string) {
    return request.get(`/vortflow/projects/${projectId}/members`);
}

/** VortFlow 添加项目成员 */
export function addVortflowProjectMember(projectId: string, data: { member_id: string; role?: string }) {
    return request.post(`/vortflow/projects/${projectId}/members`, data);
}

/** VortFlow 移除项目成员 */
export function removeVortflowProjectMember(projectId: string, memberId: string) {
    return request.delete(`/vortflow/projects/${projectId}/members/${memberId}`);
}

// -- 需求 --

/** VortFlow 需求列表 */
export function getVortflowStories(params: { project_id?: string; state?: string; keyword?: string; priority?: number; page?: number; page_size?: number }) {
    return request.get("/vortflow/stories", { params });
}

/** VortFlow 需求详情 */
export function getVortflowStory(id: string) {
    return request.get(`/vortflow/stories/${id}`);
}

/** VortFlow 创建需求 */
export function createVortflowStory(data: { project_id: string; title: string; description?: string; priority?: number; deadline?: string }) {
    return request.post("/vortflow/stories", data);
}

/** VortFlow 更新需求 */
export function updateVortflowStory(id: string, data: { title?: string; description?: string; priority?: number; deadline?: string }) {
    return request.put(`/vortflow/stories/${id}`, data);
}

/** VortFlow 删除需求 */
export function deleteVortflowStory(id: string) {
    return request.delete(`/vortflow/stories/${id}`);
}

/** VortFlow 需求状态流转 */
export function transitionVortflowStory(id: string, target_state: string) {
    return request.post(`/vortflow/stories/${id}/transition`, { target_state });
}

/** VortFlow 需求可用状态 */
export function getVortflowStoryTransitions(id: string) {
    return request.get(`/vortflow/stories/${id}/transitions`);
}

// -- 任务 --

/** VortFlow 任务列表 */
export function getVortflowTasks(params: { story_id?: string; state?: string; task_type?: string; assignee_id?: string; keyword?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/tasks", { params });
}

/** VortFlow 任务详情 */
export function getVortflowTask(id: string) {
    return request.get(`/vortflow/tasks/${id}`);
}

/** VortFlow 创建任务 */
export function createVortflowTask(data: { story_id: string; title: string; description?: string; task_type?: string; assignee_id?: string; estimate_hours?: number; deadline?: string }) {
    return request.post("/vortflow/tasks", data);
}

/** VortFlow 更新任务 */
export function updateVortflowTask(id: string, data: { title?: string; description?: string; task_type?: string; assignee_id?: string; estimate_hours?: number; actual_hours?: number; deadline?: string }) {
    return request.put(`/vortflow/tasks/${id}`, data);
}

/** VortFlow 删除任务 */
export function deleteVortflowTask(id: string) {
    return request.delete(`/vortflow/tasks/${id}`);
}

/** VortFlow 任务状态流转 */
export function transitionVortflowTask(id: string, target_state: string) {
    return request.post(`/vortflow/tasks/${id}/transition`, { target_state });
}

/** VortFlow 任务可用状态 */
export function getVortflowTaskTransitions(id: string) {
    return request.get(`/vortflow/tasks/${id}/transitions`);
}

// -- 缺陷 --

/** VortFlow 缺陷列表 */
export function getVortflowBugs(params: { story_id?: string; state?: string; severity?: number; assignee_id?: string; keyword?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/bugs", { params });
}

/** VortFlow 缺陷详情 */
export function getVortflowBug(id: string) {
    return request.get(`/vortflow/bugs/${id}`);
}

/** VortFlow 创建缺陷 */
export function createVortflowBug(data: { story_id?: string; task_id?: string; title: string; description?: string; severity?: number; assignee_id?: string }) {
    return request.post("/vortflow/bugs", data);
}

/** VortFlow 更新缺陷 */
export function updateVortflowBug(id: string, data: { title?: string; description?: string; severity?: number; assignee_id?: string }) {
    return request.put(`/vortflow/bugs/${id}`, data);
}

/** VortFlow 删除缺陷 */
export function deleteVortflowBug(id: string) {
    return request.delete(`/vortflow/bugs/${id}`);
}

/** VortFlow 缺陷状态流转 */
export function transitionVortflowBug(id: string, target_state: string) {
    return request.post(`/vortflow/bugs/${id}/transition`, { target_state });
}

/** VortFlow 缺陷可用状态 */
export function getVortflowBugTransitions(id: string) {
    return request.get(`/vortflow/bugs/${id}/transitions`);
}

// -- 里程碑 --

/** VortFlow 里程碑列表 */
export function getVortflowMilestones(params: { project_id?: string; keyword?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/milestones", { params });
}

/** VortFlow 里程碑详情 */
export function getVortflowMilestone(id: string) {
    return request.get(`/vortflow/milestones/${id}`);
}

/** VortFlow 创建里程碑 */
export function createVortflowMilestone(data: { project_id: string; name: string; description?: string; due_date?: string; story_id?: string }) {
    return request.post("/vortflow/milestones", data);
}

/** VortFlow 更新里程碑 */
export function updateVortflowMilestone(id: string, data: { name?: string; description?: string; due_date?: string; completed_at?: string }) {
    return request.put(`/vortflow/milestones/${id}`, data);
}

/** VortFlow 删除里程碑 */
export function deleteVortflowMilestone(id: string) {
    return request.delete(`/vortflow/milestones/${id}`);
}

/** VortFlow 完成里程碑 */
export function completeVortflowMilestone(id: string) {
    return request.post(`/vortflow/milestones/${id}/complete`);
}

// -- 事件日志 --

/** VortFlow 事件日志 */
export function getVortflowEvents(params: { entity_type?: string; entity_id?: string; page?: number; page_size?: number }) {
    return request.get("/vortflow/events", { params });
}

// ==================== VortGit ====================

// -- Git 平台 --

/** VortGit 平台列表 */
export function getVortgitProviders() {
    return request.get("/vortgit/providers", {
        params: { _t: Date.now() }
    });
}

/** VortGit 平台详情 */
export function getVortgitProvider(id: string) {
    return request.get(`/vortgit/providers/${id}`);
}

/** VortGit 创建平台 */
export function createVortgitProvider(data: { name: string; platform: string; api_base?: string; access_token?: string; is_default?: boolean }) {
    return request.post("/vortgit/providers", data);
}

/** VortGit 更新平台 */
export function updateVortgitProvider(id: string, data: { name?: string; platform?: string; api_base?: string; access_token?: string; is_default?: boolean }) {
    return request.put(`/vortgit/providers/${id}`, data);
}

/** VortGit 删除平台 */
export function deleteVortgitProvider(id: string) {
    return request.delete(`/vortgit/providers/${id}`);
}

/** VortGit 从平台拉取远程仓库列表 */
export function getVortgitRemoteRepos(providerId: string, params: { page?: number; per_page?: number; search?: string }) {
    return request.get(`/vortgit/providers/${providerId}/remote-repos`, { params });
}

// -- Git 仓库 --

/** VortGit 仓库列表 */
export function getVortgitRepos(params: { provider_id?: string; project_id?: string; keyword?: string; page?: number; page_size?: number }) {
    return request.get("/vortgit/repos", { params });
}

/** VortGit 仓库详情 */
export function getVortgitRepo(id: string) {
    return request.get(`/vortgit/repos/${id}`);
}

/** VortGit 创建仓库 */
export function createVortgitRepo(data: { provider_id: string; name: string; full_name: string; clone_url?: string; ssh_url?: string; default_branch?: string; description?: string; language?: string; repo_type?: string; is_private?: boolean; project_id?: string }) {
    return request.post("/vortgit/repos", data);
}

/** VortGit 更新仓库 */
export function updateVortgitRepo(id: string, data: { name?: string; description?: string; repo_type?: string; project_id?: string; default_branch?: string }) {
    return request.put(`/vortgit/repos/${id}`, data);
}

/** VortGit 删除仓库 */
export function deleteVortgitRepo(id: string) {
    return request.delete(`/vortgit/repos/${id}`);
}

/** VortGit 批量导入仓库 */
export function importVortgitRepos(data: { provider_id: string; repos: { full_name: string; project_id?: string; repo_type?: string }[] }) {
    return request.post("/vortgit/repos/import", data);
}

/** VortGit 同步仓库信息 */
export function syncVortgitRepo(id: string) {
    return request.post(`/vortgit/repos/${id}/sync`);
}

/** VortGit 仓库提交记录 */
export function getVortgitRepoCommits(id: string, params: { branch?: string; since?: string; until?: string; author?: string; page?: number; per_page?: number }) {
    return request.get(`/vortgit/repos/${id}/commits`, { params });
}

/** VortGit 仓库分支 */
export function getVortgitRepoBranches(id: string) {
    return request.get(`/vortgit/repos/${id}/branches`);
}

// -- 仓库成员 --

/** VortGit 仓库成员列表 */
export function getVortgitRepoMembers(repoId: string) {
    return request.get(`/vortgit/repos/${repoId}/members`);
}

/** VortGit 添加仓库成员 */
export function addVortgitRepoMember(repoId: string, data: { member_id: string; access_level?: string; platform_username?: string }) {
    return request.post(`/vortgit/repos/${repoId}/members`, data);
}

/** VortGit 移除仓库成员 */
export function removeVortgitRepoMember(repoId: string, memberId: string) {
    return request.delete(`/vortgit/repos/${repoId}/members/${memberId}`);
}

// -- AI 编码任务 --

/** VortGit 编码任务列表 */
export function getVortgitCodeTasks(params: { status?: string; repo_id?: string; member_id?: string; page?: number; page_size?: number }) {
    return request.get("/vortgit/code-tasks", { params });
}

/** VortGit 编码任务详情 */
export function getVortgitCodeTask(id: string) {
    return request.get(`/vortgit/code-tasks/${id}`);
}

/** VortGit 编码任务统计 */
export function getVortgitCodeTaskStats() {
    return request.get("/vortgit/code-tasks/stats");
}

/** VortGit 编码环境状态 */
export function getVortgitCodingEnvStatus() {
    return request.get("/vortgit/coding-env/status");
}

// ====== 汇报管理 ======

// -- 汇报模板 --

/** 汇报模板列表 */
export function getReportTemplates() {
    return request.get("/reports/templates");
}

/** 创建汇报模板 */
export function createReportTemplate(data: { name: string; report_type: string; content_schema?: object; auto_collect?: object }) {
    return request.post("/reports/templates", data);
}

/** 删除汇报模板 */
export function deleteReportTemplate(id: string) {
    return request.delete(`/reports/templates/${id}`);
}

// -- 汇报规则 --

/** 汇报规则列表 */
export function getReportRules(templateId?: string) {
    return request.get("/reports/rules", { params: { template_id: templateId } });
}

/** 创建汇报规则 */
export function createReportRule(data: { template_id: string; scope: string; target_id: string; reviewer_id?: string; deadline_cron?: string; reminder_minutes?: number; escalation_minutes?: number; enabled?: boolean }) {
    return request.post("/reports/rules", data);
}

/** 删除汇报规则 */
export function deleteReportRule(id: string) {
    return request.delete(`/reports/rules/${id}`);
}

// -- 汇报 --

/** 汇报列表 */
export function getReports(params: { report_type?: string; status?: string; since?: string; until?: string; reporter_id?: string; reviewer_id?: string; page?: number; page_size?: number }) {
    return request.get("/reports", { params });
}

/** 汇报详情 */
export function getReportDetail(id: string) {
    return request.get(`/reports/${id}`);
}

/** 提交汇报 */
export function submitReport(data: { report_type: string; report_date?: string; title: string; content: string; template_id?: string; reviewer_id?: string }) {
    return request.post("/reports", data);
}

/** 更新汇报 */
export function updateReport(id: string, data: { title?: string; content?: string; reviewer_id?: string }) {
    return request.put(`/reports/${id}`, data);
}

/** 审阅汇报 */
export function reviewReport(id: string, data: { status: string; comment?: string }) {
    return request.put(`/reports/${id}/review`, data);
}

/** 汇报统计 */
export function getReportStats(params?: { reviewer_id?: string; since?: string; until?: string }) {
    return request.get("/reports/stats", { params });
}

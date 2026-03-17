import request from "@/utils/request";

// ---- Member CRUD ----

export function createMember(data: {
    name: string;
    email?: string;
    phone?: string;
    position?: string;
    bio?: string;
    is_account?: boolean;
    is_virtual?: boolean;
    virtual_role?: string;
    posts?: string[];
    skills?: string[];
    auto_report?: boolean;
    report_frequency?: string;
    remote_node_id?: string;
}) {
    return request.post("/admin/members", data);
}

export function getMembers(params?: { search?: string; role?: string; department_id?: number; page?: number; size?: number; is_virtual?: boolean }) {
    return request.get("/admin/members", { params });
}

export function getMember(id: string) {
    return request.get(`/admin/members/${id}`);
}

export function updateMember(id: string, data: {
    name?: string;
    email?: string;
    phone?: string;
    position?: string;
    bio?: string;
    status?: string;
    is_account?: boolean;
    is_virtual?: boolean;
    virtual_role?: string;
    posts?: string[];
    skills?: string[];
    auto_report?: boolean;
    report_frequency?: string;
    remote_node_id?: string;
}) {
    return request.put(`/admin/members/${id}`, data);
}

export function resetMemberPassword(id: string, password?: string) {
    return request.post(`/admin/members/${id}/reset-password`, { password });
}

export function toggleMemberAccount(id: string) {
    return request.post(`/admin/members/${id}/toggle-account`);
}

export function assignMemberRole(id: string, role: string) {
    return request.post(`/admin/members/${id}/roles`, { role });
}

export function removeMemberRole(id: string, role: string) {
    return request.delete(`/admin/members/${id}/roles/${role}`);
}

export function deleteMember(id: string) {
    return request.delete(`/admin/members/${id}`);
}

// ---- Batch Operations ----

export function batchDeleteMembers(ids: string[]) {
    return request.post("/admin/members/batch/delete", { ids });
}

export function batchEnableAccount(ids: string[]) {
    return request.post("/admin/members/batch/enable-account", { ids });
}

export function batchDisableAccount(ids: string[]) {
    return request.post("/admin/members/batch/disable-account", { ids });
}

export function batchAssignRole(ids: string[], role: string) {
    return request.post("/admin/members/batch/assign-role", { ids, role });
}

export function batchRemoveRole(ids: string[], role: string) {
    return request.post("/admin/members/batch/remove-role", { ids, role });
}

export function batchAssignDept(ids: string[], deptId: number) {
    return request.post("/admin/members/batch/assign-dept", { ids, dept_id: deptId });
}

export function batchRemoveDept(ids: string[], deptId: number) {
    return request.post("/admin/members/batch/remove-dept", { ids, dept_id: deptId });
}

// ---- Role-Skill Mapping ----

export function getRoleSkills(role?: string) {
    return request.get("/admin/members/roles/skills", { params: { role } });
}

export function addRoleSkill(role: string, skillIds: string[], priority: number = 0) {
    return request.post("/admin/members/roles/skills", { role, skill_ids: skillIds, priority });
}

export function removeRoleSkill(role: string, skillId: string) {
    return request.delete("/admin/members/roles/skills", { data: { role, skill_id: skillId } });
}

export function getMemberSkillsWithSource(memberId: string) {
    return request.get(`/admin/members/${memberId}/skills`);
}

export function addMemberSkill(memberId: string, skillId: string, source: string = "public") {
    return request.post(`/admin/members/${memberId}/skills`, { skill_id: skillId, source });
}

export function updateMemberSkill(memberId: string, skillId: string, data: { enabled?: boolean; custom_content?: string }) {
    return request.put(`/admin/members/${memberId}/skills/${skillId}`, data);
}

export function removeMemberSkill(memberId: string, skillId: string) {
    return request.delete(`/admin/members/${memberId}/skills/${skillId}`);
}

// ---- Roles & Permissions ----

export function getRoles() {
    return request.get("/admin/members/roles/list");
}

export function getPermissions() {
    return request.get("/admin/members/permissions/list");
}

export function createRole(data: { name: string; display_name: string; permissions: string[] }) {
    return request.post("/admin/members/roles", data);
}

export function updateRole(roleId: number, data: { display_name?: string; permissions?: string[] }) {
    return request.put(`/admin/members/roles/${roleId}`, data);
}

export function deleteRole(roleId: number) {
    return request.delete(`/admin/members/roles/${roleId}`);
}

export function getVirtualMemberStats() {
    return request.get("/admin/members/virtual-stats");
}

// ---- Contacts Sync ----

export function getContacts() {
    return request.get("/admin/contacts");
}

export function syncContacts(channel?: string) {
    return request.post("/admin/contacts/sync", null, { params: channel ? { channel } : {} });
}

export function getSuggestions() {
    return request.get("/admin/contacts/suggestions");
}

export function acceptSuggestion(id: number) {
    return request.post(`/admin/contacts/suggestions/${id}/accept`);
}

export function rejectSuggestion(id: number) {
    return request.post(`/admin/contacts/suggestions/${id}/reject`);
}

export function mergeMembers(source_id: string, target_id: string) {
    return request.post("/admin/contacts/merge", { source_id, target_id });
}

export function dedupContacts() {
    return request.post("/admin/contacts/dedup");
}

// ---- Departments ----

export function getDepartmentTree(platform?: string) {
    return request.get("/admin/departments", { params: { platform } });
}

export function getDepartment(id: number) {
    return request.get(`/admin/departments/${id}`);
}

export function createDepartment(name: string, parent_id?: number | null) {
    return request.post("/admin/departments", { name, parent_id });
}

export function updateDepartment(id: number, data: { name?: string; parent_id?: number | null; order?: number }) {
    return request.put(`/admin/departments/${id}`, data);
}

export function deleteDepartment(id: number) {
    return request.delete(`/admin/departments/${id}`);
}

export function getDepartmentMembers(id: number) {
    return request.get(`/admin/departments/${id}/members`);
}

export function addDepartmentMember(deptId: number, memberId: string, isPrimary = false) {
    return request.post(`/admin/departments/${deptId}/members`, { member_id: memberId, is_primary: isPrimary });
}

export function removeDepartmentMember(deptId: number, memberId: string) {
    return request.delete(`/admin/departments/${deptId}/members/${memberId}`);
}

// ---- Reporting Relations ----

export function getReportingRelations(memberId?: string) {
    return request.get("/admin/reporting-relations", { params: { member_id: memberId } });
}

export function createReportingRelation(data: { reporter_id: string; supervisor_id: string; relation_type?: string; is_primary?: boolean }) {
    return request.post("/admin/reporting-relations", data);
}

export function updateReportingRelation(id: number, data: { relation_type?: string; is_primary?: boolean }) {
    return request.put(`/admin/reporting-relations/${id}`, data);
}

export function deleteReportingRelation(id: number) {
    return request.delete(`/admin/reporting-relations/${id}`);
}

export function getSubordinates(memberId: string) {
    return request.get(`/admin/reporting-relations/subordinates/${memberId}`);
}

export function getSupervisors(memberId: string) {
    return request.get(`/admin/reporting-relations/supervisors/${memberId}`);
}

// ---- Org Calendar ----

export function getOrgCalendar(year?: number) {
    return request.get("/admin/org-calendar", { params: { year } });
}

export function createOrgCalendarEntry(data: { date: string; day_type: string; name?: string }) {
    return request.post("/admin/org-calendar", data);
}

export function batchCreateOrgCalendar(entries: { date: string; day_type: string; name?: string }[]) {
    return request.post("/admin/org-calendar/batch", { entries });
}

export function deleteOrgCalendarEntry(id: number) {
    return request.delete(`/admin/org-calendar/${id}`);
}

export function syncHolidays(year?: number) {
    return request.post("/admin/org-calendar/sync-holidays", null, { params: { year } });
}

export function getWorkSettings() {
    return request.get("/admin/org-calendar/work-settings");
}

export function updateWorkSettings(data: Record<string, string>) {
    return request.put("/admin/org-calendar/work-settings", data);
}

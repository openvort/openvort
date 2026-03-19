import request from "@/utils/request";

// ---- Virtual Roles / Posts ----

export function getVirtualRoles(enabled?: boolean, page?: number, pageSize?: number) {
    return request.get("/posts", { params: { enabled, page, page_size: pageSize } });
}

export function getVirtualRole(roleKeyOrId: string) {
    return request.get(`/posts/${roleKeyOrId}`);
}

export function createVirtualRole(data: {
    key: string;
    name: string;
    description?: string;
    icon?: string;
    default_persona?: string;
    default_auto_report?: boolean;
    default_report_frequency?: string;
}) {
    return request.post("/posts", data);
}

export function updateVirtualRole(roleId: string, data: {
    name?: string;
    description?: string;
    icon?: string;
    default_persona?: string;
    default_auto_report?: boolean;
    default_report_frequency?: string;
    enabled?: boolean;
}) {
    return request.put(`/posts/${roleId}`, data);
}

export function deleteVirtualRole(roleId: string) {
    return request.delete(`/posts/${roleId}`);
}

export function getVirtualRoleSkills(roleKeyOrId: string) {
    return request.get(`/posts/${roleKeyOrId}/skills`);
}

export function bindVirtualRoleSkills(roleKeyOrId: string, data: {
    skill_ids: string[];
    priorities?: Record<string, number>;
}) {
    return request.put(`/posts/${roleKeyOrId}/skills`, data);
}

export function generateRolePersonaPrompt(roleKeyOrId: string) {
    return request.get(`/virtual-roles/${roleKeyOrId}/generate-persona-prompt`);
}

// ---- Work Assignments ----

export function getWorkAssignments(params: {
    assignee_member_id?: string;
    requested_by_member_id?: string;
    status?: string;
}) {
    return request.get("/work-assignments", { params });
}

export function createWorkAssignment(data: {
    title: string;
    summary?: string;
    plan?: string;
    assignee_member_id: string;
    requested_by_member_id?: string;
    source_type?: string;
    source_id?: string;
    source_detail?: string;
    related_schedule_id?: number;
    status?: string;
    priority?: string;
    due_date?: string;
}) {
    return request.post("/work-assignments", data);
}

export function updateWorkAssignment(assignmentId: number, data: {
    title?: string;
    summary?: string;
    plan?: string;
    source_detail?: string;
    status?: string;
    priority?: string;
    due_date?: string;
}) {
    return request.put(`/work-assignments/${assignmentId}`, data);
}

export function deleteWorkAssignment(assignmentId: number) {
    return request.delete(`/work-assignments/${assignmentId}`);
}

export function updateWorkAssignmentStatus(assignmentId: number, status: string) {
    return request.post(`/work-assignments/${assignmentId}/update_status`, null, { params: { status } });
}

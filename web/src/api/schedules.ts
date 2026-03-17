import request from "@/utils/request";

// ---- Personal Schedules ----

export function getMySchedules(params?: {
    page?: number;
    page_size?: number;
    keyword?: string;
    schedule_type?: string;
    last_status?: string;
    hide_done_once?: boolean;
}) {
    return request.get("/schedules", { params });
}

export function createMySchedule(data: {
    name: string;
    description?: string;
    schedule_type: string;
    schedule: string;
    timezone?: string;
    action_type?: string;
    action_config?: Record<string, any>;
    enabled?: boolean;
    target_member_id?: string;
}) {
    return request.post("/schedules", data);
}

export function updateMySchedule(jobId: string, data: Record<string, any>) {
    return request.put(`/schedules/${jobId}`, data);
}

export function deleteMySchedule(jobId: string) {
    return request.delete(`/schedules/${jobId}`);
}

export function batchDeleteMySchedules(jobIds: string[]) {
    return request.post("/schedules/batch-delete", { job_ids: jobIds });
}

export function toggleMySchedule(jobId: string) {
    return request.post(`/schedules/${jobId}/toggle`);
}

export function runMySchedule(jobId: string) {
    return request.post(`/schedules/${jobId}/run`);
}

export function getScheduleExecutors() {
    return request.get("/schedules/executors");
}

// ---- Admin Schedules ----

export function getAdminSchedules(params?: {
    page?: number;
    page_size?: number;
    keyword?: string;
    schedule_type?: string;
    last_status?: string;
    hide_done_once?: boolean;
}) {
    return request.get("/admin/schedules", { params });
}

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

export function updateAdminSchedule(jobId: string, data: Record<string, any>) {
    return request.put(`/admin/schedules/${jobId}`, data);
}

export function deleteAdminSchedule(jobId: string) {
    return request.delete(`/admin/schedules/${jobId}`);
}

export function batchDeleteAdminSchedules(jobIds: string[]) {
    return request.post("/admin/schedules/batch-delete", { job_ids: jobIds });
}

export function toggleAdminSchedule(jobId: string) {
    return request.post(`/admin/schedules/${jobId}/toggle`);
}

export function runAdminSchedule(jobId: string) {
    return request.post(`/admin/schedules/${jobId}/run`);
}

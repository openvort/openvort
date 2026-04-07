import request from "@/utils/request";

// ---- Publications ----

export function getPublications() {
    return request.get("/reports/publications");
}

export function createPublication(data: Record<string, any>) {
    return request.post("/reports/publications", data);
}

export function getPublication(id: string) {
    return request.get(`/reports/publications/${id}`);
}

export function updatePublication(id: string, data: Record<string, any>) {
    return request.put(`/reports/publications/${id}`, data);
}

export function deletePublication(id: string) {
    return request.delete(`/reports/publications/${id}`);
}

export function sendReminders(id: string) {
    return request.post(`/reports/publications/${id}/remind`);
}

export function sendSummary(id: string) {
    return request.post(`/reports/publications/${id}/summary`);
}

// ---- Reports ----

export function getMyPublications() {
    return request.get("/reports/my-publications");
}

export function getReports(params: Record<string, any>) {
    return request.get("/reports", { params });
}

export function getReportDetail(id: string) {
    return request.get(`/reports/${id}`);
}

export function submitReport(data: { report_type: string; report_date?: string; title: string; content: string; publication_id?: string }) {
    return request.post("/reports", data);
}

export function updateReport(id: string, data: { title?: string; content?: string }) {
    return request.put(`/reports/${id}`, data);
}

export function getReportStats(params?: Record<string, any>) {
    return request.get("/reports/stats", { params });
}

import request from "@/utils/request";

// ---- Templates ----

export function getReportTemplates() {
    return request.get("/reports/templates");
}

export function createReportTemplate(data: { name: string; description?: string; report_type: string; content_schema?: object; auto_collect?: object }) {
    return request.post("/reports/templates", data);
}

export function updateReportTemplate(id: string, data: { name: string; description?: string; report_type: string; content_schema?: object; auto_collect?: object }) {
    return request.put(`/reports/templates/${id}`, data);
}

export function deleteReportTemplate(id: string) {
    return request.delete(`/reports/templates/${id}`);
}

// ---- Rules ----

export function getReportRules(templateId?: string) {
    return request.get("/reports/rules", { params: { template_id: templateId } });
}

export function createReportRule(data: { template_id: string; member_ids: string[]; name?: string; deadline_cron?: string; workdays_only?: boolean }) {
    return request.post("/reports/rules", data);
}

export function updateReportRule(id: string, data: { member_ids?: string[]; enabled?: boolean; deadline_cron?: string; workdays_only?: boolean }) {
    return request.put(`/reports/rules/${id}`, data);
}

export function deleteReportRule(id: string) {
    return request.delete(`/reports/rules/${id}`);
}

export function testSendReportRule(id: string) {
    return request.post(`/reports/rules/${id}/test-send`);
}

// ---- Reports ----

export function getReports(params: { report_type?: string; status?: string; since?: string; until?: string; reporter_id?: string; reviewer_id?: string; page?: number; page_size?: number }) {
    return request.get("/reports", { params });
}

export function getReportDetail(id: string) {
    return request.get(`/reports/${id}`);
}

export function submitReport(data: { report_type: string; report_date?: string; title: string; content: string; template_id?: string; reviewer_id?: string }) {
    return request.post("/reports", data);
}

export function updateReport(id: string, data: { title?: string; content?: string; reviewer_id?: string }) {
    return request.put(`/reports/${id}`, data);
}

export function generateReportContentPrompt(reportType: string, reportDate?: string) {
    return request.get("/reports/generate-content-prompt", {
        params: { report_type: reportType, report_date: reportDate },
    });
}

export function reviewReport(id: string, data: { status: string; comment?: string }) {
    return request.put(`/reports/${id}/review`, data);
}

export function getReportStats(params?: { reviewer_id?: string; since?: string; until?: string }) {
    return request.get("/reports/stats", { params });
}

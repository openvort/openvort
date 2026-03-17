import request from "@/utils/request";

export function getKBDocuments(params?: { page?: number; page_size?: number; keyword?: string; status?: string }) {
    return request.get("/knowledge/documents", { params });
}

export function uploadKBDocument(file: File, title?: string) {
    const formData = new FormData();
    formData.append("file", file);
    if (title) formData.append("title", title);
    return request.post("/knowledge/documents", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
    });
}

export function createKBTextDocument(data: { title: string; content: string; file_type?: string }) {
    return request.post("/knowledge/documents/text", data);
}

export function getKBDocument(id: string) {
    return request.get(`/knowledge/documents/${id}`);
}

export function updateKBDocument(id: string, data: { title?: string; content?: string }) {
    return request.put(`/knowledge/documents/${id}`, data);
}

export function deleteKBDocument(id: string) {
    return request.delete(`/knowledge/documents/${id}`);
}

export function reindexKBDocument(id: string) {
    return request.post(`/knowledge/documents/${id}/reindex`);
}

export function searchKB(query: string, top_k: number = 5) {
    return request.post("/knowledge/search", { query, top_k });
}

export function getKBStats() {
    return request.get("/knowledge/stats");
}

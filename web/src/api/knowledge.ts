import request from "@/utils/request";

// ---- Folders ----

export function getKBFolders(parent_id: string = "") {
    return request.get("/knowledge/folders", { params: { parent_id } });
}

export function getKBFolder(id: string) {
    return request.get(`/knowledge/folders/${id}`);
}

export function createKBFolder(data: { name: string; parent_id?: string; description?: string }) {
    return request.post("/knowledge/folders", data);
}

export function updateKBFolder(id: string, data: { name?: string; parent_id?: string; description?: string }) {
    return request.put(`/knowledge/folders/${id}`, data);
}

export function deleteKBFolder(id: string) {
    return request.delete(`/knowledge/folders/${id}`);
}

export function moveKBItems(data: { folder_ids?: string[]; document_ids?: string[]; target_folder_id: string }) {
    return request.post("/knowledge/move", data);
}

// ---- Documents ----

export function getKBDocuments(params?: { page?: number; page_size?: number; keyword?: string; status?: string; folder_id?: string }) {
    return request.get("/knowledge/documents", { params });
}

export function uploadKBDocument(file: File, title?: string, folder_id?: string) {
    const formData = new FormData();
    formData.append("file", file);
    if (title) formData.append("title", title);
    if (folder_id) formData.append("folder_id", folder_id);
    return request.post("/knowledge/documents", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
    });
}

export function createKBTextDocument(data: { title: string; content: string; file_type?: string; folder_id?: string }) {
    return request.post("/knowledge/documents/text", data);
}

export function createKBGitDocument(data: { repo_id: string; branch: string; path: string; title?: string; folder_id?: string }) {
    return request.post("/knowledge/documents/git", data);
}

export function getKBDocGitContent(docId: string, branch: string) {
    return request.get(`/knowledge/documents/${docId}/git-content`, { params: { branch } });
}

export function getKBDocument(id: string) {
    return request.get(`/knowledge/documents/${id}`);
}

export function updateKBDocument(id: string, data: { title?: string; content?: string; folder_id?: string }) {
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

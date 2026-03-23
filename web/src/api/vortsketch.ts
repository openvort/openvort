import request from "@/utils/request";

// ---- Sketches ----

export function getSketches(params?: { page?: number; page_size?: number; keyword?: string; project_id?: string; is_archived?: boolean }) {
    return request.get("/sketches", { params });
}

export function getSketch(id: string) {
    return request.get(`/sketches/${id}`);
}

export function createSketch(data: { name: string; description?: string; project_id?: string; story_id?: string; story_type?: string }) {
    return request.post("/sketches", data);
}

export function updateSketch(id: string, data: { name?: string; description?: string; is_archived?: boolean }) {
    return request.patch(`/sketches/${id}`, data);
}

export function deleteSketch(id: string) {
    return request.delete(`/sketches/${id}`);
}

export function duplicateSketch(id: string) {
    return request.post(`/sketches/${id}/duplicate`);
}

// ---- Pages ----

export function getSketchPages(sketchId: string) {
    return request.get(`/sketches/${sketchId}/pages`);
}

export function getSketchPage(sketchId: string, pageId: string) {
    return request.get(`/sketches/${sketchId}/pages/${pageId}`);
}

export function createSketchPage(sketchId: string, data: { name: string }) {
    return request.post(`/sketches/${sketchId}/pages`, data);
}

export function updateSketchPage(sketchId: string, pageId: string, data: { name?: string; sort_order?: number }) {
    return request.patch(`/sketches/${sketchId}/pages/${pageId}`, data);
}

export function deleteSketchPage(sketchId: string, pageId: string) {
    return request.delete(`/sketches/${sketchId}/pages/${pageId}`);
}

export function duplicateSketchPage(sketchId: string, pageId: string) {
    return request.post(`/sketches/${sketchId}/pages/${pageId}/duplicate`);
}

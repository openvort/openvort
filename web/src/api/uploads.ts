import request from "@/utils/request";

export function uploadEditorImage(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return request.post("/uploads/editor/image", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 30000,
    });
}

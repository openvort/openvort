import { ref } from "vue";
import { uploadChatFile } from "@/api";
import { message } from "@/components/vort";
import type { PendingImage, PendingFile } from "../types";

const IMAGE_TYPES = new Set(["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]);
const ALLOWED_EXTS = new Set(["jpg", "jpeg", "png", "gif", "webp", "txt", "md", "pdf", "doc", "docx", "xls", "xlsx", "rar", "zip", "7z"]);

function getFileExt(name: string): string {
    const dot = name.lastIndexOf(".");
    return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

export function useChatImages() {
    const pendingImages = ref<PendingImage[]>([]);
    const pendingFiles = ref<PendingFile[]>([]);
    const isDragging = ref(false);

    function fileToBase64(file: File): Promise<PendingImage | null> {
        return new Promise((resolve) => {
            if (!file.type.startsWith("image/")) { resolve(null); return; }
            const reader = new FileReader();
            reader.onload = () => {
                const dataUrl = reader.result as string;
                const match = dataUrl.match(/^data:(image\/[^;]+);base64,(.+)$/);
                if (match) {
                    resolve({ data: match[2]!, media_type: match[1]!, preview: dataUrl });
                } else { resolve(null); }
            };
            reader.onerror = () => resolve(null);
            reader.readAsDataURL(file);
        });
    }

    async function uploadNonImageFile(file: File) {
        const placeholder: PendingFile = {
            file_id: "",
            filename: file.name,
            file_url: "",
            content_text: "",
            file_size: file.size,
            uploading: true,
        };
        pendingFiles.value.push(placeholder);
        const idx = pendingFiles.value.length - 1;
        try {
            const res: any = await uploadChatFile(file);
            if (res?.error) {
                message.error(res.error);
                pendingFiles.value.splice(idx, 1);
                return;
            }
            pendingFiles.value[idx] = {
                file_id: res.file_id,
                filename: res.filename,
                file_url: res.file_url,
                content_text: res.content_text || "",
                file_size: res.file_size || file.size,
                uploading: false,
            };
        } catch {
            message.error(`${file.name} upload failed`);
            pendingFiles.value.splice(idx, 1);
        }
    }

    async function addFiles(files: FileList | File[]) {
        for (const file of files) {
            const ext = getFileExt(file.name);
            if (!ALLOWED_EXTS.has(ext)) {
                message.warning(`不支持的文件类型: .${ext}`);
                continue;
            }
            if (IMAGE_TYPES.has(file.type)) {
                if (pendingImages.value.length >= 10) break;
                const img = await fileToBase64(file);
                if (img) pendingImages.value.push(img);
            } else {
                if (pendingFiles.value.length >= 5) {
                    message.warning("最多附加 5 个文件");
                    break;
                }
                uploadNonImageFile(file);
            }
        }
    }

    function removeImage(index: number) { pendingImages.value.splice(index, 1); }
    function removeFile(index: number) { pendingFiles.value.splice(index, 1); }

    function handlePaste(e: ClipboardEvent) {
        const items = e.clipboardData?.items;
        if (!items) return;
        const imageFiles: File[] = [];
        for (const item of items) {
            if (item.type.startsWith("image/")) {
                const file = item.getAsFile();
                if (file) imageFiles.push(file);
            }
        }
        if (imageFiles.length) { e.preventDefault(); addFiles(imageFiles); }
    }

    function handleDragOver(e: DragEvent) { e.preventDefault(); isDragging.value = true; }
    function handleDragLeave(e: DragEvent) { e.preventDefault(); isDragging.value = false; }
    function handleDrop(e: DragEvent) {
        e.preventDefault(); isDragging.value = false;
        const files = e.dataTransfer?.files;
        if (files?.length) addFiles(files);
    }

    return {
        pendingImages,
        pendingFiles,
        isDragging,
        fileToBase64,
        addFiles,
        removeImage,
        removeFile,
        handlePaste,
        handleDragOver,
        handleDragLeave,
        handleDrop,
    };
}

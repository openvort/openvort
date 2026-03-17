import { ref } from "vue";
import type { PendingImage } from "../types";

export function useChatImages() {
    const pendingImages = ref<PendingImage[]>([]);
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

    async function addFiles(files: FileList | File[]) {
        for (const file of files) {
            if (pendingImages.value.length >= 10) break;
            const img = await fileToBase64(file);
            if (img) pendingImages.value.push(img);
        }
    }

    function removeImage(index: number) { pendingImages.value.splice(index, 1); }

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
        isDragging,
        fileToBase64,
        addFiles,
        removeImage,
        handlePaste,
        handleDragOver,
        handleDragLeave,
        handleDrop,
    };
}

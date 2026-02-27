<script setup lang="ts">
import { ref, computed } from "vue";
import { InboxOutlined } from "@/components/vort/icons";
import Upload from "./Upload.vue";
import type { UploadFile, UploadChangeInfo, UploadRequestOption } from "./types";

defineOptions({ name: "VortUploadDragger" });

/** Vort UploadDragger - 拖拽上传组件 */

interface Props {
    /** 接受上传的文件类型 */
    accept?: string;
    /** 上传的地址 */
    action?: string;
    /** 上传请求时额外的参数 */
    data?: Record<string, unknown> | ((file: UploadFile) => Record<string, unknown>);
    /** 默认已上传的文件列表 */
    defaultFileList?: UploadFile[];
    /** 是否禁用 */
    disabled?: boolean;
    /** 已上传的文件列表（受控） */
    fileList?: UploadFile[];
    /** 设置上传的请求头部 */
    headers?: Record<string, string>;
    /** 限制上传数量 */
    maxCount?: number;
    /** 上传请求的 HTTP 方法 */
    method?: string;
    /** 是否支持多选文件 */
    multiple?: boolean;
    /** 发送到后台的文件参数名 */
    name?: string;
    /** 是否展示文件列表 */
    showUploadList?: boolean | { showPreviewIcon?: boolean; showRemoveIcon?: boolean; showDownloadIcon?: boolean };
    /** 上传请求时是否携带 Cookie */
    withCredentials?: boolean;
    /** 是否支持上传文件夹 */
    directory?: boolean;
    /** 自定义类名 */
    class?: string;
    /** 高度 */
    height?: string | number;
}

const props = withDefaults(defineProps<Props>(), {
    action: "",
    disabled: false,
    method: "post",
    multiple: true,
    name: "file",
    showUploadList: true,
    withCredentials: false,
    directory: false
});

const emit = defineEmits<{
    /** 文件状态改变的回调 */
    change: [info: UploadChangeInfo];
    /** 文件列表变化 */
    "update:fileList": [fileList: UploadFile[]];
    /** 上传文件之前的钩子 */
    beforeUpload: [file: File, fileList: File[]];
    /** 点击文件链接或预览图标时的回调 */
    preview: [file: UploadFile];
    /** 点击移除文件时的回调 */
    remove: [file: UploadFile];
    /** 点击下载文件时的回调 */
    download: [file: UploadFile];
    /** 当文件被拖入上传区域时执行的回调 */
    drop: [event: DragEvent];
}>();

// 定义可以接收的回调（用于 beforeUpload 控制）
const beforeUpload = defineModel<(file: File, fileList: File[]) => boolean | Promise<boolean | File>>("beforeUpload");
const customRequest = defineModel<(options: UploadRequestOption) => void>("customRequest");

// 拖拽状态
const isDragging = ref(false);

// 处理拖拽事件
const handleDragEnter = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (props.disabled) return;
    isDragging.value = true;
};

const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isDragging.value = false;
};

const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
};

const handleDrop = (e: DragEvent) => {
    isDragging.value = false;
    emit("drop", e);
};

// 容器样式
const containerClass = computed(() => {
    const classes = ["vort-upload-dragger"];
    if (props.disabled) classes.push("vort-upload-dragger-disabled");
    if (isDragging.value) classes.push("vort-upload-dragger-drag-hover");
    if (props.class) classes.push(props.class);
    return classes;
});

// 高度样式
const heightStyle = computed(() => {
    if (!props.height) return {};
    const h = typeof props.height === "number" ? `${props.height}px` : props.height;
    return { height: h };
});
</script>

<template>
    <Upload
        v-bind="props"
        :before-upload="beforeUpload"
        :custom-request="customRequest"
        list-type="text"
        class="vort-upload-dragger-wrapper"
        @change="emit('change', $event)"
        @update:file-list="emit('update:fileList', $event)"
        @preview="emit('preview', $event)"
        @remove="emit('remove', $event)"
        @download="emit('download', $event)"
        @drop="handleDrop"
    >
        <div :class="containerClass" :style="heightStyle" @dragenter="handleDragEnter" @dragleave="handleDragLeave" @dragover="handleDragOver">
            <slot>
                <div class="vort-upload-dragger-content">
                    <p class="vort-upload-dragger-icon">
                        <InboxOutlined />
                    </p>
                    <p class="vort-upload-dragger-text">Click or drag file to this area to upload</p>
                    <p class="vort-upload-dragger-hint">
                        Support for a single or bulk upload. Strictly prohibited from uploading company data or other banned files.
                    </p>
                </div>
            </slot>
        </div>
    </Upload>
</template>

<style scoped>
.vort-upload-dragger-wrapper {
    display: block;
    width: 100%;
}

.vort-upload-dragger {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 180px;
    padding: 24px;
    text-align: center;
    background: #fafafa;
    border: 1px dashed var(--vort-border);
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    cursor: pointer;
    transition:
        border-color 0.2s,
        background-color 0.2s;
}

.vort-upload-dragger:hover {
    border-color: var(--vort-primary);
}

.vort-upload-dragger-disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

.vort-upload-dragger-disabled:hover {
    border-color: var(--vort-border);
}

.vort-upload-dragger-drag-hover {
    border-color: var(--vort-primary);
    background: var(--vort-primary-bg);
}

.vort-upload-dragger-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
}

.vort-upload-dragger-icon {
    margin: 0;
    font-size: 48px;
    color: var(--vort-primary);
}

.vort-upload-dragger-text {
    margin: 0;
    font-size: 16px;
    color: var(--vort-text);
}

.vort-upload-dragger-hint {
    margin: 0;
    font-size: 14px;
    color: var(--vort-text-secondary);
}
</style>

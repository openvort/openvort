<script setup lang="ts">
import { ref, computed, watch } from "vue";
import {
    UploadOutlined,
    PlusOutlined,
    LoadingOutlined,
    DeleteOutlined,
    DownloadOutlined,
    EyeOutlined,
    PaperClipOutlined,
    FileOutlined,
    PictureOutlined
} from "@/components/vort/icons";
import type { UploadFile, UploadChangeInfo, UploadRequestOption, UploadListType } from "./types";

defineOptions({ name: "VortUpload" });

/** Vort Upload - 上传组件 */

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
    /** 上传列表的内建样式 */
    listType?: UploadListType;
    /** 限制上传数量 */
    maxCount?: number;
    /** 上传请求的 HTTP 方法 */
    method?: string;
    /** 是否支持多选文件 */
    multiple?: boolean;
    /** 发送到后台的文件参数名 */
    name?: string;
    /** 自定义上传按钮文字 */
    placeholder?: string;
    /** 是否展示文件列表 */
    showUploadList?: boolean | { showPreviewIcon?: boolean; showRemoveIcon?: boolean; showDownloadIcon?: boolean };
    /** 上传请求时是否携带 Cookie */
    withCredentials?: boolean;
    /** 点击文件链接或预览图标时的回调 */
    openFileDialogOnClick?: boolean;
    /** 是否支持上传文件夹 */
    directory?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    action: "",
    disabled: false,
    listType: "text",
    method: "post",
    multiple: false,
    name: "file",
    placeholder: "Upload",
    showUploadList: true,
    withCredentials: false,
    openFileDialogOnClick: true,
    directory: false
});

const emit = defineEmits<{
    /** 文件状态改变的回调 */
    change: [info: UploadChangeInfo];
    /** 文件列表变化 */
    "update:fileList": [fileList: UploadFile[]];
    /** 文件列表变化（兼容 kebab-case，用于 v-model:file-list） */
    "update:file-list": [fileList: UploadFile[]];
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

// 内部文件列表
const internalFileList = ref<UploadFile[]>(props.defaultFileList || []);

// 使用 fileList prop 或内部状态
const fileList = computed({
    get: () => {
        // 受控模式下（props.fileList 有传），如果父组件没及时回写导致一直是空数组，
        // 不要用空数组把内部列表“清空掉”，否则会表现为“选完立刻没了/不回显”。
        if (props.fileList !== undefined) {
            return props.fileList.length ? props.fileList : internalFileList.value;
        }
        return internalFileList.value;
    },
    set: (val) => {
        internalFileList.value = val;
        emit("update:fileList", val);
        // Vue 模板里更常见的是 v-model:file-list，它会监听 update:file-list
        emit("update:file-list", val);
    }
});

// 同步外部 fileList
watch(
    () => props.fileList,
    (val) => {
        if (val !== undefined) {
            // 如果父组件传回空数组，但内部已有文件（常见于 v-model 没接上/异步回写），保留内部列表
            if (Array.isArray(val) && val.length === 0 && internalFileList.value.length > 0) return;
            internalFileList.value = val;
        }
    }
);

// Input ref
const inputRef = ref<HTMLInputElement | null>(null);

// 拖拽状态
const isDragging = ref(false);

// 生成唯一ID
const generateUid = () => `upload-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

// 是否为图片
const isImageFile = (file: UploadFile | File): boolean => {
    const type = (file as UploadFile).type || (file as File).type || "";
    return type.startsWith("image/");
};

// 获取文件缩略图
const getThumbUrl = (file: UploadFile): string => {
    if (file.thumbUrl) return file.thumbUrl;
    if (file.url) return file.url;
    if (file.originFileObj && isImageFile(file)) {
        return URL.createObjectURL(file.originFileObj);
    }
    return "";
};

// 是否显示上传按钮（根据 maxCount 判断）
const showUploadButton = computed(() => {
    if (props.maxCount === undefined) return true;
    return fileList.value.length < props.maxCount;
});

// 处理文件选择
const handleFileChange = async (e: Event) => {
    const target = e.target as HTMLInputElement;
    const files = Array.from(target.files || []);
    if (!files.length) return;

    await processFiles(files);

    // 清空 input，允许重复选择相同文件
    target.value = "";
};

// 处理文件
const processFiles = async (files: File[]) => {
    // 限制数量
    let filesToProcess = files;
    if (props.maxCount !== undefined) {
        const totalCount = fileList.value.length + files.length;
        if (totalCount > props.maxCount) {
            const overflow = totalCount - props.maxCount;
            if (overflow >= fileList.value.length) {
                fileList.value = [];
            } else if (overflow > 0) {
                fileList.value = fileList.value.slice(overflow);
            }
        }

        const remaining = props.maxCount - fileList.value.length;
        filesToProcess = files.slice(0, remaining);
    }

    for (const file of filesToProcess) {
        // beforeUpload 钩子
        if (beforeUpload.value) {
            try {
                const result = await beforeUpload.value(file, filesToProcess);
                if (result === false) continue;
                // 如果返回的是文件对象，使用返回的文件
                if (result instanceof File) {
                    await uploadFile(result);
                    continue;
                }
            } catch {
                continue;
            }
        }

        await uploadFile(file);
    }
};

// 上传单个文件
const uploadFile = async (file: File) => {
    const uploadFile: UploadFile = {
        uid: generateUid(),
        name: file.name,
        status: "uploading",
        percent: 0,
        originFileObj: file,
        type: file.type,
        size: file.size
    };

    // 添加到文件列表
    const newFileList = [...fileList.value, uploadFile];
    fileList.value = newFileList;

    emitChange(uploadFile, newFileList);

    // 如果有自定义上传
    if (customRequest.value) {
        customRequest.value({
            action: props.action,
            data: typeof props.data === "function" ? props.data(uploadFile) : props.data,
            file,
            filename: props.name,
            headers: props.headers,
            withCredentials: props.withCredentials,
            onProgress: (event) => {
                updateFileStatus(uploadFile.uid, { percent: event.percent });
            },
            onSuccess: (response) => {
                updateFileStatus(uploadFile.uid, { status: "done", response });
            },
            onError: (error) => {
                updateFileStatus(uploadFile.uid, { status: "error", error });
            }
        });
        return;
    }

    // 默认上传逻辑
    if (props.action) {
        try {
            const formData = new FormData();
            formData.append(props.name, file);

            // 添加额外参数
            const data = typeof props.data === "function" ? props.data(uploadFile) : props.data;
            if (data) {
                Object.entries(data).forEach(([key, value]) => {
                    formData.append(key, String(value));
                });
            }

            const xhr = new XMLHttpRequest();

            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    updateFileStatus(uploadFile.uid, { percent });
                }
            };

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    let response;
                    try {
                        response = JSON.parse(xhr.responseText);
                    } catch {
                        response = xhr.responseText;
                    }
                    updateFileStatus(uploadFile.uid, { status: "done", response, percent: 100 });
                } else {
                    updateFileStatus(uploadFile.uid, { status: "error", error: new Error(xhr.statusText) });
                }
            };

            xhr.onerror = () => {
                updateFileStatus(uploadFile.uid, { status: "error", error: new Error("Upload failed") });
            };

            xhr.open(props.method.toUpperCase(), props.action);

            // 设置请求头
            if (props.headers) {
                Object.entries(props.headers).forEach(([key, value]) => {
                    xhr.setRequestHeader(key, value);
                });
            }

            xhr.withCredentials = props.withCredentials;
            xhr.send(formData);
        } catch (error) {
            updateFileStatus(uploadFile.uid, { status: "error", error });
        }
    } else {
        // 没有 action，直接标记为完成
        updateFileStatus(uploadFile.uid, { status: "done", percent: 100 });
    }
};

// 更新文件状态
const updateFileStatus = (uid: string, updates: Partial<UploadFile>) => {
    const newFileList = fileList.value.map((file) => {
        if (file.uid === uid) {
            const updatedFile = { ...file, ...updates };
            emitChange(updatedFile, fileList.value);
            return updatedFile;
        }
        return file;
    });
    fileList.value = newFileList;
};

// 发送变化事件
const emitChange = (file: UploadFile, fileList: UploadFile[], event?: ProgressEvent) => {
    emit("change", { file, fileList, event });
};

// 移除文件
const handleRemove = (file: UploadFile) => {
    emit("remove", file);
    const newFileList = fileList.value.filter((f) => f.uid !== file.uid);
    fileList.value = newFileList;
    emitChange({ ...file, status: "removed" }, newFileList);
};

// 预览文件
const handlePreview = (file: UploadFile) => {
    emit("preview", file);
};

// 下载文件
const handleDownload = (file: UploadFile) => {
    emit("download", file);
    if (file.url) {
        const a = document.createElement("a");
        a.href = file.url;
        a.download = file.name;
        a.target = "_blank";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }
};

// 点击上传区域
const handleClick = () => {
    if (props.disabled || !props.openFileDialogOnClick) return;
    inputRef.value?.click();
};

// 拖拽事件
const handleDragEnter = (e: DragEvent) => {
    e.preventDefault();
    if (props.disabled) return;
    isDragging.value = true;
};

const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    isDragging.value = false;
};

const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
};

const handleDrop = async (e: DragEvent) => {
    e.preventDefault();
    isDragging.value = false;
    if (props.disabled) return;

    emit("drop", e);

    const files = Array.from(e.dataTransfer?.files || []);
    if (files.length) {
        await processFiles(files);
    }
};

// 计算显示上传列表的选项
const showUploadListOptions = computed(() => {
    if (typeof props.showUploadList === "boolean") {
        return props.showUploadList
            ? { showPreviewIcon: true, showRemoveIcon: true, showDownloadIcon: false }
            : { showPreviewIcon: false, showRemoveIcon: false, showDownloadIcon: false };
    }
    return {
        showPreviewIcon: props.showUploadList.showPreviewIcon ?? true,
        showRemoveIcon: props.showUploadList.showRemoveIcon ?? true,
        showDownloadIcon: props.showUploadList.showDownloadIcon ?? false
    };
});

// 是否为卡片类型
const isCardType = computed(() => props.listType === "picture-card" || props.listType === "picture-circle");

// 容器样式
const containerClass = computed(() => {
    const classes = ["vort-upload", `vort-upload-${props.listType}`];
    if (props.disabled) classes.push("vort-upload-disabled");
    if (isDragging.value) classes.push("vort-upload-drag-hover");
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div :class="containerClass">
        <!-- 隐藏的文件输入 -->
        <input
            ref="inputRef"
            type="file"
            :accept="accept"
            :multiple="multiple"
            :disabled="disabled"
            :webkitdirectory="directory || undefined"
            class="vort-upload-input"
            @change="handleFileChange"
        />

        <!-- 卡片类型：图片墙/圆形 -->
        <template v-if="isCardType">
            <div class="vort-upload-list vort-upload-list-card">
                <!-- 已上传的文件列表 -->
                <div
                    v-for="file in fileList"
                    :key="file.uid"
                    class="vort-upload-list-item"
                    :class="[`vort-upload-list-item-${file.status || 'done'}`, listType === 'picture-circle' && 'vort-upload-list-item-circle']"
                >
                    <!-- 缩略图 -->
                    <div class="vort-upload-list-item-thumbnail">
                        <template v-if="file.status === 'uploading'">
                            <LoadingOutlined class="vort-upload-list-item-loading" />
                        </template>
                        <template v-else-if="isImageFile(file) && getThumbUrl(file)">
                            <img :src="getThumbUrl(file)" :alt="file.name" class="vort-upload-list-item-image" />
                        </template>
                        <template v-else>
                            <FileOutlined class="vort-upload-list-item-file-icon" />
                        </template>
                    </div>

                    <!-- 操作按钮 -->
                    <div class="vort-upload-list-item-actions">
                        <button
                            v-if="showUploadListOptions.showPreviewIcon && file.status === 'done'"
                            type="button"
                            class="vort-upload-list-item-action"
                            @click="handlePreview(file)"
                        >
                            <EyeOutlined />
                        </button>
                        <button v-if="showUploadListOptions.showRemoveIcon" type="button" class="vort-upload-list-item-action" @click="handleRemove(file)">
                            <DeleteOutlined />
                        </button>
                    </div>

                    <!-- 进度条 -->
                    <div v-if="file.status === 'uploading'" class="vort-upload-list-item-progress">
                        <div class="vort-upload-list-item-progress-bar" :style="{ width: `${file.percent || 0}%` }" />
                    </div>

                    <!-- 错误提示 -->
                    <div v-if="file.status === 'error'" class="vort-upload-list-item-error">
                        {{ file.name }}
                    </div>
                </div>

                <!-- 上传按钮 -->
                <div
                    v-if="showUploadButton"
                    class="vort-upload-select"
                    :class="[listType === 'picture-circle' && 'vort-upload-select-circle']"
                    @click="handleClick"
                    @dragenter="handleDragEnter"
                    @dragleave="handleDragLeave"
                    @dragover="handleDragOver"
                    @drop="handleDrop"
                >
                    <slot>
                        <div class="vort-upload-select-content">
                            <PlusOutlined class="vort-upload-select-icon" />
                            <span class="vort-upload-select-text">{{ placeholder || "Upload" }}</span>
                        </div>
                    </slot>
                </div>
            </div>
        </template>

        <!-- 普通类型：按钮触发 -->
        <template v-else>
            <!-- 触发区域 -->
            <div
                class="vort-upload-select"
                @click="handleClick"
                @dragenter="handleDragEnter"
                @dragleave="handleDragLeave"
                @dragover="handleDragOver"
                @drop="handleDrop"
            >
                <slot>
                    <button type="button" class="vort-upload-btn" :disabled="disabled">
                        <UploadOutlined />
                        <span>{{ placeholder }}</span>
                    </button>
                </slot>
            </div>

            <!-- 文件列表 -->
            <div v-if="props.showUploadList && fileList.length" class="vort-upload-list vort-upload-list-text">
                <div v-for="file in fileList" :key="file.uid" class="vort-upload-list-item" :class="[`vort-upload-list-item-${file.status || 'done'}`]">
                    <!-- 图标 -->
                    <span class="vort-upload-list-item-icon">
                        <template v-if="file.status === 'uploading'">
                            <LoadingOutlined class="vort-upload-list-item-spin" />
                        </template>
                        <template v-else-if="listType === 'picture' && isImageFile(file)">
                            <img v-if="getThumbUrl(file)" :src="getThumbUrl(file)" :alt="file.name" class="vort-upload-list-item-thumb" />
                            <PictureOutlined v-else />
                        </template>
                        <template v-else>
                            <PaperClipOutlined />
                        </template>
                    </span>

                    <!-- 文件名 -->
                    <span class="vort-upload-list-item-name" :title="file.name" @click="handlePreview(file)">
                        {{ file.name }}
                    </span>

                    <!-- 操作按钮 -->
                    <span class="vort-upload-list-item-actions">
                        <button
                            v-if="showUploadListOptions.showDownloadIcon && file.status === 'done' && file.url"
                            type="button"
                            class="vort-upload-list-item-action"
                            @click.stop="handleDownload(file)"
                        >
                            <DownloadOutlined />
                        </button>
                        <button v-if="showUploadListOptions.showRemoveIcon" type="button" class="vort-upload-list-item-action" @click.stop="handleRemove(file)">
                            <DeleteOutlined />
                        </button>
                    </span>

                    <!-- 进度条 -->
                    <div v-if="file.status === 'uploading'" class="vort-upload-list-item-progress">
                        <div class="vort-upload-list-item-progress-bar" :style="{ width: `${file.percent || 0}%` }" />
                    </div>
                </div>
            </div>
        </template>
    </div>
</template>

<style scoped>
.vort-upload {
    display: inline-block;
}

.vort-upload-input {
    display: none;
}

.vort-upload-disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

/* 上传按钮 */
.vort-upload-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 32px;
    padding: 0 16px;
    font-size: 14px;
    color: var(--vort-text);
    background: #fff;
    border: 1px solid var(--vort-border);
    border-radius: var(--vort-border-radius, 6px);
    cursor: pointer;
    transition: all 0.2s;
}

.vort-upload-btn:hover:not(:disabled) {
    color: var(--vort-primary);
    border-color: var(--vort-primary);
}

.vort-upload-btn:disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

/* 文件列表 - 文本类型 */
.vort-upload-list-text {
    margin-top: 8px;
}

.vort-upload-list-text .vort-upload-list-item {
    display: flex;
    align-items: center;
    height: 24px;
    padding: 4px 8px;
    margin-bottom: 4px;
    font-size: 14px;
    border-radius: var(--vort-border-radius-sm, 4px);
    transition: background-color 0.2s;
}

.vort-upload-list-text .vort-upload-list-item:hover {
    background: rgba(0, 0, 0, 0.04);
}

.vort-upload-list-item-icon {
    display: inline-flex;
    align-items: center;
    margin-right: 8px;
    color: var(--vort-text-secondary);
}

.vort-upload-list-item-thumb {
    width: 24px;
    height: 24px;
    object-fit: cover;
    border-radius: var(--vort-border-radius-sm, 2px);
}

.vort-upload-list-item-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--vort-text);
    cursor: pointer;
}

.vort-upload-list-item-name:hover {
    color: var(--vort-primary);
}

.vort-upload-list-item-actions {
    display: flex;
    gap: 4px;
    margin-left: 8px;
    opacity: 0;
    transition: opacity 0.2s;
}

.vort-upload-list-item:hover .vort-upload-list-item-actions {
    opacity: 1;
}

.vort-upload-list-item-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    padding: 0;
    color: var(--vort-text-secondary);
    background: transparent;
    border: none;
    cursor: pointer;
    transition: color 0.2s;
}

.vort-upload-list-item-action:hover {
    color: var(--vort-primary);
}

/* 进度条 */
.vort-upload-list-item-progress {
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 2px;
    background: var(--vort-border);
}

.vort-upload-list-item-progress-bar {
    height: 100%;
    background: var(--vort-primary);
    transition: width 0.2s;
}

.vort-upload-list-text .vort-upload-list-item {
    position: relative;
}

.vort-upload-list-text .vort-upload-list-item-progress {
    bottom: -2px;
    border-radius: 0 0 var(--vort-border-radius-sm, 4px) var(--vort-border-radius-sm, 4px);
}

/* 状态样式 */
.vort-upload-list-item-error {
    color: var(--vort-error);
}

.vort-upload-list-item-error .vort-upload-list-item-name {
    color: var(--vort-error);
}

.vort-upload-list-item-error .vort-upload-list-item-icon {
    color: var(--vort-error);
}

/* 卡片类型 */
.vort-upload-picture-card,
.vort-upload-picture-circle {
    display: block;
}

.vort-upload-list-card {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.vort-upload-list-card .vort-upload-list-item {
    position: relative;
    width: 104px;
    height: 104px;
    padding: 8px;
    background: #fafafa;
    border: 1px solid var(--vort-border);
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    cursor: pointer;
    transition: border-color 0.2s;
}

.vort-upload-list-card .vort-upload-list-item:hover {
    border-color: var(--vort-primary);
}

.vort-upload-list-card .vort-upload-list-item-circle {
    border-radius: 50%;
}

.vort-upload-list-item-thumbnail {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
}

.vort-upload-list-item-image {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: var(--vort-border-radius-sm, 4px);
}

.vort-upload-list-item-circle .vort-upload-list-item-image {
    border-radius: 50%;
}

.vort-upload-list-item-loading {
    font-size: 24px;
    color: var(--vort-primary);
    animation: vort-spin 1s linear infinite;
}

.vort-upload-list-item-file-icon {
    font-size: 32px;
    color: var(--vort-text-secondary);
}

/* 卡片操作按钮 */
.vort-upload-list-card .vort-upload-list-item-actions {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin: 0;
    background: rgba(0, 0, 0, 0.5);
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 7px));
    opacity: 0;
    transition: opacity 0.2s;
}

.vort-upload-list-card .vort-upload-list-item-circle .vort-upload-list-item-actions {
    border-radius: 50%;
}

.vort-upload-list-card .vort-upload-list-item:hover .vort-upload-list-item-actions {
    opacity: 1;
}

.vort-upload-list-card .vort-upload-list-item-action {
    width: 24px;
    height: 24px;
    color: #fff;
    font-size: 16px;
}

.vort-upload-list-card .vort-upload-list-item-action:hover {
    color: #fff;
    transform: scale(1.1);
}

/* 卡片进度条 */
.vort-upload-list-card .vort-upload-list-item-progress {
    position: absolute;
    bottom: 8px;
    left: 8px;
    right: 8px;
    width: auto;
    height: 2px;
    border-radius: 1px;
}

/* 上传选择器（卡片类型） */
.vort-upload-select {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.vort-upload-picture-card .vort-upload-select,
.vort-upload-picture-circle .vort-upload-select {
    width: 104px;
    height: 104px;
    background: #fafafa;
    border: 1px dashed var(--vort-border);
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    transition: border-color 0.2s;
}

.vort-upload-picture-card .vort-upload-select:hover,
.vort-upload-picture-circle .vort-upload-select:hover {
    border-color: var(--vort-primary);
}

.vort-upload-select-circle {
    border-radius: 50% !important;
}

.vort-upload-select-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    color: var(--vort-text-secondary);
}

.vort-upload-select-icon {
    font-size: 20px;
}

.vort-upload-select-text {
    font-size: 14px;
}

/* 拖拽悬浮状态 */
.vort-upload-drag-hover .vort-upload-select {
    border-color: var(--vort-primary);
    background: var(--vort-primary-bg);
}

/* 错误状态卡片 */
.vort-upload-list-card .vort-upload-list-item-error {
    border-color: var(--vort-error);
}

.vort-upload-list-card .vort-upload-list-item-error .vort-upload-list-item-error {
    position: absolute;
    bottom: 4px;
    left: 4px;
    right: 4px;
    padding: 2px 4px;
    font-size: 12px;
    color: #fff;
    background: var(--vort-error);
    border-radius: var(--vort-border-radius-sm, 2px);
    text-overflow: ellipsis;
    overflow: hidden;
    white-space: nowrap;
}

/* 文本列表加载旋转 */
.vort-upload-list-item-spin {
    animation: vort-spin 1s linear infinite;
}

/* 动画 */
@keyframes vort-spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}
</style>

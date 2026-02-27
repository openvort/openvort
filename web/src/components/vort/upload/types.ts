/**
 * Upload 组件类型定义
 */

/** 文件状态 */
export type UploadFileStatus = "uploading" | "done" | "error" | "removed";

/** 列表类型 */
export type UploadListType = "text" | "picture" | "picture-card" | "picture-circle";

/** 显示上传列表配置 */
export interface ShowUploadListOptions {
    /** 是否显示预览图标 */
    showPreviewIcon?: boolean;
    /** 是否显示移除图标 */
    showRemoveIcon?: boolean;
    /** 是否显示下载图标 */
    showDownloadIcon?: boolean;
}

/** 显示上传列表类型 */
export type ShowUploadList = boolean | ShowUploadListOptions;

/** 文件列表项 */
export interface UploadFile {
    /** 唯一标识 */
    uid: string;
    /** 文件名 */
    name: string;
    /** 文件状态 */
    status?: UploadFileStatus;
    /** 上传进度 */
    percent?: number;
    /** 文件URL（上传成功后） */
    url?: string;
    /** 缩略图URL */
    thumbUrl?: string;
    /** 原始文件对象 */
    originFileObj?: File;
    /** 响应数据 */
    response?: unknown;
    /** 错误信息 */
    error?: unknown;
    /** 文件类型 */
    type?: string;
    /** 文件大小 */
    size?: number;
}

/** 上传变化信息 */
export interface UploadChangeInfo {
    file: UploadFile;
    fileList: UploadFile[];
    event?: ProgressEvent;
}

/** 自定义请求参数 */
export interface UploadRequestOption {
    action: string;
    data?: Record<string, unknown>;
    file: File;
    filename: string;
    headers?: Record<string, string>;
    withCredentials?: boolean;
    onProgress?: (event: { percent: number }) => void;
    onSuccess?: (response: unknown, file: File) => void;
    onError?: (error: Error) => void;
}

/** beforeUpload 钩子函数类型 */
export type BeforeUploadFn = (file: File, fileList: File[]) => boolean | Promise<boolean | File>;

/** customRequest 自定义请求函数类型 */
export type CustomRequestFn = (options: UploadRequestOption) => void;

/** Upload 组件 Props */
export interface UploadProps {
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
    /** 是否展示文件列表 */
    showUploadList?: ShowUploadList;
    /** 上传请求时是否携带 Cookie */
    withCredentials?: boolean;
    /** 点击是否打开文件选择对话框 */
    openFileDialogOnClick?: boolean;
    /** 是否支持上传文件夹 */
    directory?: boolean;
    /** 自定义类名 */
    class?: string;
}

/** Upload 组件 Emits */
export interface UploadEmits {
    /** 文件状态改变的回调 */
    (e: "change", info: UploadChangeInfo): void;
    /** 文件列表变化（用于 v-model:fileList） */
    (e: "update:fileList", fileList: UploadFile[]): void;
    /** 文件列表变化（用于 v-model:file-list） */
    (e: "update:file-list", fileList: UploadFile[]): void;
    /** 上传文件之前的钩子 */
    (e: "beforeUpload", file: File, fileList: File[]): void;
    /** 点击文件链接或预览图标时的回调 */
    (e: "preview", file: UploadFile): void;
    /** 点击移除文件时的回调 */
    (e: "remove", file: UploadFile): void;
    /** 点击下载文件时的回调 */
    (e: "download", file: UploadFile): void;
    /** 当文件被拖入上传区域时执行的回调 */
    (e: "drop", event: DragEvent): void;
}

/** UploadDragger 组件 Props */
export interface UploadDraggerProps extends Omit<UploadProps, "listType" | "openFileDialogOnClick"> {
    /** 拖拽区域高度 */
    height?: string | number;
}

/** UploadDragger 组件 Emits */
export interface UploadDraggerEmits {
    /** 文件状态改变的回调 */
    (e: "change", info: UploadChangeInfo): void;
    /** 文件列表变化 */
    (e: "update:fileList", fileList: UploadFile[]): void;
    /** 上传文件之前的钩子 */
    (e: "beforeUpload", file: File, fileList: File[]): void;
    /** 点击文件链接或预览图标时的回调 */
    (e: "preview", file: UploadFile): void;
    /** 点击移除文件时的回调 */
    (e: "remove", file: UploadFile): void;
    /** 点击下载文件时的回调 */
    (e: "download", file: UploadFile): void;
    /** 当文件被拖入上传区域时执行的回调 */
    (e: "drop", event: DragEvent): void;
}
